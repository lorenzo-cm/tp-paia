from app.db.models.conversations import MessageUpdate
from app.services.agent.base import AgentAttachment
from app.services.message_processing.attachment_service import AttachmentService
from app.services.message_processing.deps import Repos
from app.services.message_processing.protocols import MediaFetcher
from app.services.message_processing.schemas import ConversationContext, Enriched
from app.services.storage import R2Service


async def enrich_attachments(
    context: ConversationContext,
    repos: Repos,
    media_fetcher: MediaFetcher,
    attachment_service: AttachmentService,
    r2: R2Service,
) -> Enriched:
    """Upload attachments, transcribe/extract, update ``Message.content``, collect agent files."""
    combined_parts: list[str] = []
    agent_attachments: list[AgentAttachment] = []
    for _inbound, message, attachments in context.items:
        texts: list[str] = []
        for att in attachments:
            stored = await attachment_service.store(
                att,
                context.conversation_id,
                message.id,
                media_fetcher,
                r2,
                repos.message_attachment,
            )
            if stored is None:
                continue
            res = await attachment_service.extract(stored)
            if res.text is not None:
                texts.append(res.text)
            if res.agent_attachment is not None:
                agent_attachments.append(res.agent_attachment)
        original = message.content or ""
        derived = "\n".join(t for t in [original, *texts] if t.strip())
        if derived != original:
            repos.message.update(MessageUpdate(id=message.id, content=derived))
        if derived.strip():
            combined_parts.append(derived)
    return Enriched("\n".join(combined_parts), agent_attachments)
