from typing import Any

from openai import APIError, AsyncOpenAI

from app.services.nsfw.base import (
    BaseNSFWFilter,
    ModerationResult,
)
from app.services.nsfw.exceptions import NSFWError


class OpenAINSFWFilter(BaseNSFWFilter):
    """OpenAI Moderation backed by omni-moderation-latest.

    Single endpoint handles text and image inputs (free, low latency).
    """

    def __init__(self, *, api_key: str) -> None:
        if not api_key:
            raise NSFWError("api_key is required")
        self._client = AsyncOpenAI(api_key=api_key)

    async def is_safe_text(self, text: str) -> ModerationResult:
        return await self._moderate(input=text)

    async def is_safe_image(self, image_url: str) -> ModerationResult:
        return await self._moderate(
            input=[{"type": "image_url", "image_url": {"url": image_url}}]
        )

    async def _moderate(self, *, input: Any) -> ModerationResult:
        try:
            response = await self._client.moderations.create(
                model="omni-moderation-latest",
                input=input,
            )
        except APIError as e:
            raise NSFWError("OpenAI moderation call failed") from e
        result = response.results[0]
        flagged = [k for k, v in result.categories.model_dump().items() if v]
        return ModerationResult(is_safe=not result.flagged, flagged_categories=flagged)
