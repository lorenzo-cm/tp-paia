from functools import lru_cache

from app.core.config import get_settings
from app.services.nsfw import BaseNSFWFilter
from app.services.nsfw.exceptions import NSFWError
from app.services.nsfw.openai_moderation import OpenAINSFWFilter


@lru_cache(maxsize=1)
def get_nsfw_filter() -> BaseNSFWFilter | None:
    settings = get_settings()
    if settings.NSFW_PROVIDER == "openai_moderation":
        if not settings.OPENAI_API_KEY:
            raise NSFWError("OPENAI_API_KEY not configured")
        return OpenAINSFWFilter(api_key=settings.OPENAI_API_KEY)
    return None
