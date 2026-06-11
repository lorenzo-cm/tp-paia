import asyncio
import time

from sqlmodel import Session

from app.db.models.conversations import MessageCreate, SenderType
from app.services.agent.base import AgentAttachment, BaseAgent
from app.services.message_processing.deps import Repos
from app.services.message_processing.protocols import OutboundSender
from app.services.message_processing.schemas import ConversationContext, Enriched
from app.services.nsfw.base import BaseNSFWFilter


async def moderate(
    enriched: Enriched,
    context: ConversationContext,
    repos: Repos,
    db: Session,
    sender: OutboundSender,
    nsfw: BaseNSFWFilter | None,
    agent: BaseAgent,
    *,
    response_started: float,
) -> bool:
    """Check content safety. Returns ``True`` when the pipeline should stop.

    Unsafe text: LLM refusal persisted and sent to the channel.
    Unsafe images: removed from ``enriched.agent_attachments``; run continues.
    No filter configured: always returns ``False``.
    """
    if nsfw is None:
        return False
    if enriched.combined_text.strip():
        result = await nsfw.is_safe_text(enriched.combined_text)
        if not result.is_safe:
            response = await agent.decline_unsafe_input()
            repos.message.create(
                MessageCreate(
                    conversation_id=context.conversation_id,
                    sender_participant_id=context.bot_participant_id,
                    sender_type=SenderType.ASSISTANT,
                    content=response.text,
                )
            )
            db.commit()
            await asyncio.to_thread(
                sender.send_message, context.conv_ext_id, response.text
            )
            response_time_ms = int((time.monotonic() - response_started) * 1000)
            repos.metric.record_response_time(context.conversation_id, response_time_ms)
            db.commit()
            return True
    safe: list[AgentAttachment] = []
    for att in enriched.agent_attachments:
        if att.file_type == "image":
            image_result = await nsfw.is_safe_image(att.url)
            if not image_result.is_safe:
                continue
        safe.append(att)
    enriched.agent_attachments = safe
    return False
