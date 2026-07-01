import logging

from app.core.logger import log_context
from app.services.chatwoot.media_fetcher import ChatwootMediaFetcher
from app.services.chatwoot.schemas.webhook import ChatwootWebhook
from app.services.chatwoot.webhook_mapper import map_webhook_to_inbound
from app.services.message_processing.pipeline import MessagePipeline
from app.services.message_processing.protocols import OutboundSender

logger = logging.getLogger(__name__)


class ChatwootWebhookProcessor:
    """Inbound webhook path: filter → map → message pipeline"""

    def __init__(
        self,
        pipeline: MessagePipeline,
        sender: OutboundSender,
        media_fetcher: ChatwootMediaFetcher,
    ) -> None:
        self._pipeline = pipeline
        self._sender = sender
        self._media_fetcher = media_fetcher

    async def process(self, webhook: ChatwootWebhook) -> None:
        with log_context(
            external_conversation_id=webhook.conversation.id,
            contact_external_id=webhook.sender.id,
            inbox_id=webhook.inbox.id,
        ):
            try:
                if not self._should_process_webhook(webhook):
                    return
                dto = map_webhook_to_inbound(webhook)
                await self._pipeline.process(dto, self._sender, self._media_fetcher)
            except Exception:
                logger.exception(
                    "chatwoot webhook processing failed webhook_id=%s", webhook.id
                )

    def _should_process_webhook(self, webhook: ChatwootWebhook) -> bool:
        """Filters out non-incoming messages."""
        return webhook.is_incoming_message()
