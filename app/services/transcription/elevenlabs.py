import asyncio
import io

from elevenlabs.client import ElevenLabs

from app.services.transcription.base import (
    BaseTranscriptor,
    TranscriptionError,
    TranscriptionResult,
)


class ElevenLabsTranscriptor(BaseTranscriptor):
    """ElevenLabs Scribe via sync SDK + asyncio.to_thread."""

    def __init__(self, *, api_key: str, model: str) -> None:
        if not api_key:
            raise TranscriptionError("api_key is required")
        self._client = ElevenLabs(api_key=api_key)
        self._model = model

    async def _do_transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        def _sync_call() -> TranscriptionResult:
            audio_data = io.BytesIO(audio_bytes)
            result = self._client.speech_to_text.convert(
                model_id=self._model,
                file=audio_data,
                tag_audio_events=True,
            )
            language = _normalize_language_code(getattr(result, "language_code", None))
            return TranscriptionResult(text=result.text, language=language)

        return await asyncio.to_thread(_sync_call)


_ELEVENLABS_LANG_CODE_TO_STD = {
    "en": "en",
    "eng": "en",
    "pt": "pt",
    "por": "pt",
    "fr": "fr",
    "fra": "fr",
    "fre": "fr",
    "es": "es",
    "spa": "es",
    "de": "de",
    "deu": "de",
    "ger": "de",
    "ja": "ja",
    "jpn": "ja",
}

def _normalize_language_code(language_code: str | None) -> str | None:
    if not language_code:
        return None
    return _ELEVENLABS_LANG_CODE_TO_STD.get(
        language_code.lower(), language_code.lower()
    )

