from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.http import download_bytes


@dataclass
class TranscriptionResult:
    text: str
    language: str | None = None


class TranscriptionError(Exception):
    """Raised when transcription fails or configuration is invalid."""


class BaseTranscriptor(ABC):
    """Template base: `transcribe` normalizes input; subclasses implement `_do_transcribe`."""

    async def transcribe(self, audio: bytes | str) -> TranscriptionResult:
        if isinstance(audio, str):
            audio_bytes = await download_bytes(audio)
        else:
            audio_bytes = audio
        return await self._do_transcribe(audio_bytes)

    @abstractmethod
    async def _do_transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        ...
