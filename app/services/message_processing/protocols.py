from typing import Protocol, runtime_checkable

from app.services.message_processing.schemas import InboundAttachment


@runtime_checkable
class OutboundSender(Protocol):
    """Send a reply back to the user on the channel."""

    def send_message(
        self,
        conversation_id: int,
        message: str = "",
        attachments: list[str] | None = None,
    ) -> None: ...


@runtime_checkable
class MediaFetcher(Protocol):
    """Fetch raw bytes for an inbound attachment."""

    async def fetch(self, attachment: InboundAttachment) -> bytes: ...
