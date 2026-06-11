import logging
import time

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.db.config import engine as default_engine
from app.services.agent.base import BaseAgent
from app.services.message_debouncer.service import MessageDebouncer
from app.services.message_processing import steps
from app.services.message_processing.attachment_service import AttachmentService
from app.services.message_processing.deps import Repos
from app.services.message_processing.protocols import MediaFetcher, OutboundSender
from app.services.message_processing.schemas import InboundMessage
from app.services.nsfw.base import BaseNSFWFilter
from app.services.storage import R2Service

logger = logging.getLogger(__name__)


class MessagePipeline:
    """Channel-agnostic orchestrator for one inbound user message.

    Entry point: ``process(msg, sender, media_fetcher)`` with a mapped
    ``InboundMessage``. Per call: ``sender`` and ``media_fetcher`` (channel).
    At init: debouncer, attachments, NSFW, agent, R2.

    Steps (see ``process`` and ``steps/``):

    1. Debounce — coalesce rapid messages; exit early if not the final burst.
    2. Save user messages — resolve conversation and write USER rows to the DB.
    3. Enrich — store attachments, transcribe audio, extract documents.
    4. RAG — index enriched content for retrieval.
    5. Moderate — block unsafe text (LLM refusal) or drop unsafe images.
    6. Invoke agent — run the LLM, persist and send the reply.

    Owns the only DB ``Session`` per run. No channel imports.
    """

    def __init__(
        self,
        debouncer: MessageDebouncer,
        attachment_service: AttachmentService,
        nsfw: BaseNSFWFilter | None,
        agent: BaseAgent,
        r2: R2Service,
        *,
        agent_history_limit: int,
        engine: Engine = default_engine,
    ) -> None:
        self._debouncer = debouncer
        self._attachments = attachment_service
        self._nsfw = nsfw
        self._agent = agent
        self._r2 = r2
        self._agent_history_limit = agent_history_limit
        self._engine = engine

    async def process(
        self,
        msg: InboundMessage,
        sender: OutboundSender,
        media_fetcher: MediaFetcher,
    ) -> None:
        response_started = time.monotonic()
        batch = await steps.debounce(self._debouncer, msg)
        if batch is None:
            return
        with Session(self._engine) as db:
            repos = Repos(db)

            context = steps.save_user_messages(batch, repos)

            enriched = await steps.enrich_attachments(
                context, repos, media_fetcher, self._attachments, self._r2
            )

            steps.rag_index(enriched, repos)

            if await steps.moderate(
                enriched,
                context,
                repos,
                db,
                sender,
                self._nsfw,
                self._agent,
                response_started=response_started,
            ):
                return

            await steps.invoke_agent(
                enriched,
                context,
                repos,
                db,
                sender,
                self._agent,
                agent_history_limit=self._agent_history_limit,
                response_started=response_started,
            )
