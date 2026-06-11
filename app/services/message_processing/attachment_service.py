import logging
from pathlib import Path
from uuid import UUID, uuid4

import magic

from app.db.models.conversations import MessageAttachmentCreate
from app.db.repositories import MessageAttachmentRepository
from app.services.agent.base import AgentAttachment
from app.services.document_processor.base import BaseDocumentProcessor
from app.services.message_processing.protocols import MediaFetcher
from app.services.message_processing.schemas import (
    ExtractResult,
    InboundAttachment,
    StoredAttachment,
)
from app.services.storage import R2Service
from app.services.transcription.base import BaseTranscriptor

logger = logging.getLogger(__name__)


class AttachmentService:
    def __init__(
        self,
        transcriptor: BaseTranscriptor,
        document_processor: BaseDocumentProcessor | None,
        *,
        max_attachment_bytes: int,
        max_document_bytes: int,
    ) -> None:
        self._transcriptor = transcriptor
        self._document_processor = document_processor
        self._max_attachment_bytes = max_attachment_bytes
        self._max_document_bytes = max_document_bytes

    async def store(
        self,
        att: InboundAttachment,
        conversation_id: UUID,
        message_id: UUID,
        media_fetcher: MediaFetcher,
        r2: R2Service,
        attachment_repo: MessageAttachmentRepository,
    ) -> StoredAttachment | None:
        """Fetch, enforce size cap, upload to R2, persist row. None if dropped."""
        try:
            data = await media_fetcher.fetch(att)
        except Exception:
            logger.exception("attachment fetch failed media_ref=%s", att.media_ref)
            return None

        if len(data) > self._max_attachment_bytes:
            logger.warning(
                "attachment dropped: %d bytes exceeds MAX_ATTACHMENT_BYTES",
                len(data),
            )
            return None

        mime: str = magic.from_buffer(data, mime=True)
        ext = self._extension_for(data, att.filename)
        key = f"{conversation_id}/{message_id}/{uuid4()}{ext}"
        try:
            r2.upload_bytes(data, key)
            url = r2.get_public_url(key)
        except Exception:
            logger.exception("R2 upload failed key=%s", key)
            return None

        try:
            attachment_repo.create(
                MessageAttachmentCreate(
                    message_id=message_id,
                    external_attachment_id=None,
                    url=url,
                    mime_type=mime,
                    size_bytes=len(data),
                )
            )
        except Exception:
            logger.exception("attachment persist failed key=%s", key)

        return StoredAttachment(data=data, mime=mime, url=url, file_type=att.file_type)

    @staticmethod
    def _extension_for(data: bytes, filename: str | None) -> str:
        guessed_ext = magic.Magic(extension=True).from_buffer(data)
        if isinstance(guessed_ext, str) and guessed_ext:
            return guessed_ext
        if filename and Path(filename).suffix:
            return Path(filename).suffix
        return ".bin"

    async def extract(self, stored: StoredAttachment) -> ExtractResult:
        """Transcribe audio, pass images/PDFs to the agent, or extract document text."""
        if stored.file_type == "audio":
            try:
                result = await self._transcriptor.transcribe(stored.data)
                return ExtractResult(text=result.text)
            except Exception:
                logger.exception("transcription failed")
                return ExtractResult()

        if stored.file_type == "image":
            return ExtractResult(
                agent_attachment=AgentAttachment(
                    file_type="image", mime_type=stored.mime, url=stored.url
                )
            )

        if stored.mime == "application/pdf" and self._document_processor is None:
            return ExtractResult(
                agent_attachment=AgentAttachment(
                    file_type="pdf", mime_type=stored.mime, url=stored.url
                )
            )
        if self._document_processor is not None:
            if len(stored.data) > self._max_document_bytes:
                logger.warning(
                    "document skipped: %d bytes exceeds MAX_DOCUMENT_BYTES",
                    len(stored.data),
                )
                return ExtractResult()
            try:
                text = await self._document_processor.process(stored.data)
                return ExtractResult(text=text)
            except Exception:
                logger.exception("document processing failed")
                return ExtractResult()

        logger.warning("office doc skipped: processor disabled (mime=%s)", stored.mime)
        return ExtractResult()
