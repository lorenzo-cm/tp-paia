from functools import lru_cache

from app.core.config import get_settings
from app.services.agent.factory import get_agent
from app.services.document_processor.factory import get_document_processor
from app.services.message_debouncer.factory import get_message_debouncer
from app.services.message_processing.attachment_service import AttachmentService
from app.services.message_processing.pipeline import MessagePipeline
from app.services.nsfw.factory import get_nsfw_filter
from app.services.storage.r2.factory import get_r2_service
from app.services.transcription.factory import get_transcriptor


@lru_cache(maxsize=1)
def get_attachment_service() -> AttachmentService:
    settings = get_settings()
    return AttachmentService(
        get_transcriptor(),
        get_document_processor(),
        max_attachment_bytes=settings.MAX_ATTACHMENT_BYTES,
        max_document_bytes=settings.MAX_DOCUMENT_BYTES,
    )


@lru_cache(maxsize=1)
def get_pipeline() -> MessagePipeline:
    settings = get_settings()
    return MessagePipeline(
        get_message_debouncer(),
        get_attachment_service(),
        get_nsfw_filter(),
        get_agent(),
        get_r2_service(),
        agent_history_limit=settings.AGENT_HISTORY_LIMIT,
    )
