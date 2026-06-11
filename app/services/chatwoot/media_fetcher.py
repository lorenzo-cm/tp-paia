from app.core.http import download_bytes
from app.services.message_processing.schemas import InboundAttachment


class ChatwootMediaFetcher:
    """``MediaFetcher`` port: plain GET on Chatwoot's public ``data_url``."""

    async def fetch(self, attachment: InboundAttachment) -> bytes:
        if attachment.url is None:
            raise ValueError("Chatwoot media fetch requires attachment.url")
        return await download_bytes(attachment.url)
