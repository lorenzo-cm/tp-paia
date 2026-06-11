import logging
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.db.models.conversations import MessageAttachmentCreate
from app.services.message_processing.attachment_service import AttachmentService
from app.services.message_processing.schemas import (
    ExtractResult,
    InboundAttachment,
    StoredAttachment,
)
from app.services.transcription.base import TranscriptionResult

settings = get_settings()

_BYTES = b"some attachment payload bytes"


# --- fakes ----------------------------------------------------------------


class FakeMediaFetcher:
    def __init__(self, data: bytes = _BYTES, *, raises: bool = False) -> None:
        self._data = data
        self._raises = raises

    async def fetch(self, attachment: InboundAttachment) -> bytes:
        if self._raises:
            raise RuntimeError("fetch boom")
        return self._data


class FakeR2:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises
        self.uploaded: list[tuple[bytes, str]] = []

    def upload_bytes(self, data: bytes, r2_path: str) -> None:
        if self._raises:
            raise RuntimeError("r2 boom")
        self.uploaded.append((data, r2_path))

    def get_public_url(self, r2_path: str) -> str:
        return f"https://r2.test/{r2_path}"


class FakeAttachmentRepo:
    def __init__(self, *, raises: bool = False) -> None:
        self._raises = raises
        self.created: list[MessageAttachmentCreate] = []

    def create(
        self, create_model: MessageAttachmentCreate, **_: Any
    ) -> MessageAttachmentCreate:
        if self._raises:
            raise RuntimeError("db boom")
        self.created.append(create_model)
        return create_model


class FakeTranscriptor:
    def __init__(self, text: str = "TRANSCRIBED", *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises

    async def transcribe(self, audio: bytes | str) -> TranscriptionResult:
        if self._raises:
            raise RuntimeError("transcribe boom")
        return TranscriptionResult(text=self._text)


class FakeDocumentProcessor:
    def __init__(self, text: str = "DOC TEXT", *, raises: bool = False) -> None:
        self._text = text
        self._raises = raises

    async def process(self, file_input: bytes | str) -> str:
        if self._raises:
            raise RuntimeError("doc boom")
        return self._text


def _att(file_type: str = "file", filename: str | None = None) -> InboundAttachment:
    return InboundAttachment(
        file_type=file_type,  # type: ignore[arg-type]
        media_ref="ref-1",
        filename=filename,
    )


def _service(
    *,
    transcriptor: Any | None = None,
    document_processor: Any = None,
) -> AttachmentService:
    return AttachmentService(
        transcriptor or FakeTranscriptor(),
        document_processor,
        max_attachment_bytes=settings.MAX_ATTACHMENT_BYTES,
        max_document_bytes=settings.MAX_DOCUMENT_BYTES,
    )


# --- store ----------------------------------------------------------------


async def test_store_happy_uploads_persists_and_returns_stored() -> None:
    conv, msg = uuid4(), uuid4()
    r2 = FakeR2()
    repo = FakeAttachmentRepo()
    svc = _service()

    stored = await svc.store(
        _att("image"),
        conv,
        msg,
        FakeMediaFetcher(),
        r2,
        repo,  # type: ignore[arg-type]
    )

    assert stored is not None
    assert stored.data == _BYTES
    assert stored.file_type == "image"
    assert len(r2.uploaded) == 1
    uploaded_data, key = r2.uploaded[0]
    assert uploaded_data == _BYTES
    assert key.startswith(f"{conv}/{msg}/")
    assert stored.url == f"https://r2.test/{key}"
    assert len(repo.created) == 1
    row = repo.created[0]
    assert row.message_id == msg
    assert row.external_attachment_id is None
    assert row.url == stored.url
    assert row.mime_type == stored.mime
    assert row.size_bytes == len(_BYTES)


async def test_store_fetch_failure_returns_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc = _service()
    with caplog.at_level(logging.ERROR):
        result = await svc.store(
            _att(),
            uuid4(),
            uuid4(),
            FakeMediaFetcher(raises=True),
            FakeR2(),  # type: ignore[arg-type]
            FakeAttachmentRepo(),  # type: ignore[arg-type]
        )
    assert result is None
    assert "attachment fetch failed" in caplog.text


async def test_store_over_max_bytes_returns_none(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "MAX_ATTACHMENT_BYTES", 4)
    r2 = FakeR2()
    repo = FakeAttachmentRepo()
    svc = _service()

    with caplog.at_level(logging.WARNING):
        result = await svc.store(
            _att(),
            uuid4(),
            uuid4(),
            FakeMediaFetcher(b"way too many bytes"),
            r2,  # type: ignore[arg-type]
            repo,  # type: ignore[arg-type]
        )

    assert result is None
    assert "exceeds MAX_ATTACHMENT_BYTES" in caplog.text
    assert r2.uploaded == []
    assert repo.created == []


async def test_store_r2_failure_returns_none(
    caplog: pytest.LogCaptureFixture,
) -> None:
    repo = FakeAttachmentRepo()
    svc = _service()
    with caplog.at_level(logging.ERROR):
        result = await svc.store(
            _att(),
            uuid4(),
            uuid4(),
            FakeMediaFetcher(),
            FakeR2(raises=True),  # type: ignore[arg-type]
            repo,  # type: ignore[arg-type]
        )
    assert result is None
    assert "R2 upload failed" in caplog.text
    assert repo.created == []


async def test_store_persistence_failure_does_not_abort(
    caplog: pytest.LogCaptureFixture,
) -> None:
    r2 = FakeR2()
    svc = _service()
    with caplog.at_level(logging.ERROR):
        stored = await svc.store(
            _att("image"),
            uuid4(),
            uuid4(),
            FakeMediaFetcher(),
            r2,  # type: ignore[arg-type]
            FakeAttachmentRepo(raises=True),  # type: ignore[arg-type]
        )
    assert stored is not None
    assert stored.data == _BYTES
    assert len(r2.uploaded) == 1
    assert "attachment persist failed" in caplog.text


# --- extract --------------------------------------------------------------


async def test_extract_audio_returns_transcribed_text() -> None:
    svc = _service(transcriptor=FakeTranscriptor("HELLO AUDIO"))
    stored = StoredAttachment(data=b"a", mime="audio/ogg", url="u", file_type="audio")

    res = await svc.extract(stored)

    assert res == ExtractResult(text="HELLO AUDIO")


async def test_extract_image_returns_agent_attachment() -> None:
    svc = _service()
    stored = StoredAttachment(
        data=b"i", mime="image/png", url="https://r2.test/x.png", file_type="image"
    )

    res = await svc.extract(stored)

    assert res.text is None
    assert res.agent_attachment is not None
    assert res.agent_attachment.file_type == "image"
    assert res.agent_attachment.mime_type == "image/png"
    assert res.agent_attachment.url == "https://r2.test/x.png"


async def test_extract_pdf_without_processor_is_agent_attachment() -> None:
    svc = _service(document_processor=None)
    stored = StoredAttachment(
        data=b"%PDF",
        mime="application/pdf",
        url="https://r2.test/d.pdf",
        file_type="file",
    )

    res = await svc.extract(stored)

    assert res.text is None
    assert res.agent_attachment is not None
    assert res.agent_attachment.file_type == "pdf"
    assert res.agent_attachment.mime_type == "application/pdf"


async def test_extract_file_with_processor_returns_text() -> None:
    svc = _service(document_processor=FakeDocumentProcessor("EXTRACTED"))
    stored = StoredAttachment(
        data=b"docx",
        mime="application/vnd.openxmlformats",
        url="u",
        file_type="file",
    )

    res = await svc.extract(stored)

    assert res == ExtractResult(text="EXTRACTED")


async def test_extract_pdf_with_processor_is_processed_as_text() -> None:
    svc = _service(document_processor=FakeDocumentProcessor("PDF TEXT"))
    stored = StoredAttachment(
        data=b"%PDF", mime="application/pdf", url="u", file_type="file"
    )

    res = await svc.extract(stored)

    assert res == ExtractResult(text="PDF TEXT")


async def test_extract_office_without_processor_is_dropped_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc = _service(document_processor=None)
    stored = StoredAttachment(
        data=b"docx",
        mime="application/vnd.openxmlformats",
        url="u",
        file_type="file",
    )

    with caplog.at_level(logging.WARNING):
        res = await svc.extract(stored)

    assert res == ExtractResult()
    assert "office doc skipped" in caplog.text


async def test_extract_transcription_failure_returns_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc = _service(transcriptor=FakeTranscriptor(raises=True))
    stored = StoredAttachment(data=b"a", mime="audio/ogg", url="u", file_type="audio")

    with caplog.at_level(logging.ERROR):
        res = await svc.extract(stored)

    assert res == ExtractResult()
    assert "transcription failed" in caplog.text


async def test_extract_document_failure_returns_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc = _service(document_processor=FakeDocumentProcessor(raises=True))
    stored = StoredAttachment(
        data=b"docx", mime="application/pdf", url="u", file_type="file"
    )

    with caplog.at_level(logging.ERROR):
        res = await svc.extract(stored)

    assert res == ExtractResult()
    assert "document processing failed" in caplog.text


async def test_extract_document_over_max_bytes_returns_empty(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(settings, "MAX_DOCUMENT_BYTES", 4)
    processor = FakeDocumentProcessor("SHOULD NOT RUN")
    svc = _service(document_processor=processor)
    stored = StoredAttachment(
        data=b"way too many bytes", mime="application/pdf", url="u", file_type="file"
    )

    with caplog.at_level(logging.WARNING):
        res = await svc.extract(stored)

    assert res == ExtractResult()
    assert "exceeds MAX_DOCUMENT_BYTES" in caplog.text
