import asyncio

import magic
from openai import OpenAI

from app.core.media.convert_audio import to_mp3
from app.services.transcription.base import (
    BaseTranscriptor,
    TranscriptionError,
    TranscriptionResult,
)


class OpenAITranscriptor(BaseTranscriptor):
    """OpenAI Speech-to-Text via sync client + asyncio.to_thread (non-blocking event loop)."""

    _MAX_BYTES = 25 * 1024 * 1024
    _MIME_TO_EXTENSION = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/mp4": "mp4",
        "audio/m4a": "m4a",
        "audio/x-m4a": "m4a",
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/webm": "webm",
        "audio/ogg": "ogg",
        "audio/opus": "opus",
    }
    _OPENAI_SUPPORTED_EXTENSIONS = {"mp3", "mp4", "mpeg", "mpga", "m4a", "wav", "webm"}

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise TranscriptionError("api_key is required")
        self._client = OpenAI(api_key=api_key)
        self._model = model

    async def _do_transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        if len(audio_bytes) > self._MAX_BYTES:
            raise TranscriptionError("Audio exceeds 25MB OpenAI limit")

        mime_type = magic.from_buffer(audio_bytes, mime=True)
        extension = self._MIME_TO_EXTENSION.get(mime_type, "bin")
        if extension not in self._OPENAI_SUPPORTED_EXTENSIONS:
            audio_bytes = to_mp3(audio_bytes, extension)
            extension = "mp3"

        def _sync_call() -> TranscriptionResult:
            result = self._client.audio.transcriptions.create(
                model=self._model,
                file=(f"audio.{extension}", audio_bytes),
            )
            return TranscriptionResult(text=result.text)

        return await asyncio.to_thread(_sync_call)
