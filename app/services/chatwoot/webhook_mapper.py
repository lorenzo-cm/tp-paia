from typing import Literal

from app.services.chatwoot.schemas.webhook import ChatwootWebhook
from app.services.message_processing.schemas import (
    InboundAttachment,
    InboundMessage,
)


def _map_file_type(file_type: str) -> Literal["image", "audio", "file"]:
    if file_type == "image":
        return "image"
    if file_type == "audio":
        return "audio"
    return "file"


def map_webhook_to_inbound(webhook: ChatwootWebhook) -> InboundMessage:
    """Map one ``ChatwootWebhook`` to the engine ``InboundMessage`` DTO.

    Pure mapping only — no I/O or DB. Debounce runs later inside the pipeline.
    """
    attachments = tuple(
        InboundAttachment(
            file_type=_map_file_type(a.file_type),
            media_ref=a.data_url,
            url=a.data_url,
            filename=a.data_url.split("/")[-1],
            mime_type=None,  # resolved later via magic in the pipeline
            size_bytes=a.file_size,
        )
        for a in webhook.attachments
    )
    return InboundMessage(
        external_message_id=str(webhook.id),
        external_conversation_id=str(webhook.conversation.id),
        inbox_ref=str(webhook.inbox.id),
        contact_external_id=str(webhook.sender.id),
        contact_name=webhook.sender.name,
        contact_phone=webhook.sender.phone_number,
        text=webhook.content or "",
        attachments=attachments,
    )
