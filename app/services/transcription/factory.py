from functools import lru_cache

from app.core.config import get_settings
from app.services.transcription import (
    BaseTranscriptor,
    ElevenLabsTranscriptor,
    OpenAITranscriptor,
    TranscriptionError,
)


@lru_cache(maxsize=1)
def get_transcriptor() -> BaseTranscriptor:
    settings = get_settings()
    if settings.TRANSCRIPTION_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise TranscriptionError("OPENAI_API_KEY not configured")
        return OpenAITranscriptor(
            api_key=settings.OPENAI_API_KEY,
            model=settings.OPENAI_TRANSCRIPTION_MODEL,
        )
    if not settings.ELEVENLABS_API_KEY:
        raise TranscriptionError("ELEVENLABS_API_KEY not configured")
    return ElevenLabsTranscriptor(
        api_key=settings.ELEVENLABS_API_KEY,
        model=settings.ELEVENLABS_TRANSCRIPTION_MODEL,
    )
