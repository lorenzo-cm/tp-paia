from functools import lru_cache

from app.core.config import get_settings
from app.services.chatwoot import ChatwootClient
from app.services.chatwoot.media_fetcher import ChatwootMediaFetcher
from app.services.chatwoot.webhook_processor import ChatwootWebhookProcessor
from app.services.message_processing.factory import get_pipeline


@lru_cache(maxsize=1)
def get_chatwoot_client() -> ChatwootClient:
    settings = get_settings()
    return ChatwootClient(
        api_url=settings.CHATWOOT_API_URL,
        api_key=settings.CHATWOOT_API_KEY,
        account_id=settings.CHATWOOT_ACCOUNT_ID,
    )


@lru_cache(maxsize=1)
def get_chatwoot_webhook_processor() -> ChatwootWebhookProcessor:
    return ChatwootWebhookProcessor(
        get_pipeline(),
        get_chatwoot_client(),
        ChatwootMediaFetcher(),
    )
