"""Tests for BaseTranscriptor contract: ABC enforcement and transcribe() routing."""

import pytest

from app.services.transcription.base import BaseTranscriptor, TranscriptionResult


class FakeTranscriptor(BaseTranscriptor):
    def __init__(self) -> None:
        self.received: bytes | None = None

    async def _do_transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        self.received = audio_bytes
        return TranscriptionResult(text="ok", language="en")


class TestBaseTranscriptorContract:

    def test_cannot_be_instantiated_directly(self) -> None:
        with pytest.raises(TypeError):
            BaseTranscriptor()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_hook_is_called_with_audio_bytes(self) -> None:
        t = FakeTranscriptor()
        await t.transcribe(b"audio")
        assert t.received == b"audio"

    @pytest.mark.asyncio
    async def test_transcribe_with_bytes_returns_result(self) -> None:
        result = await FakeTranscriptor().transcribe(b"audio")
        assert isinstance(result, TranscriptionResult)

    @pytest.mark.asyncio
    async def test_transcribe_with_url_returns_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_download(_url: str) -> bytes:
            return b"audio"

        monkeypatch.setattr("app.services.transcription.base.download_bytes", fake_download)

        result = await FakeTranscriptor().transcribe("https://example.com/audio.ogg")
        assert isinstance(result, TranscriptionResult)
