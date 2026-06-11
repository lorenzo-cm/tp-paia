from functools import lru_cache

from app.core.config import get_settings
from app.services.message_debouncer.service import MessageDebouncer


@lru_cache(maxsize=1)
def get_message_debouncer() -> MessageDebouncer:
    settings = get_settings()
    return MessageDebouncer(
        wait_time=settings.DEBOUNCE_WAIT_TIME,
        max_attempts=settings.DEBOUNCE_MAX_ATTEMPTS,
        max_messages=settings.DEBOUNCE_MAX_MESSAGES,
    )
