"""Channel-neutral inbound message contract (dataclasses, no I/O)."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import TypeAdapter


@dataclass(frozen=True)
class InboundAttachment:
    """One attachment in engine vocabulary (``media_ref`` / optional ``url``)."""

    file_type: Literal["image", "audio", "file"]
    media_ref: str
    url: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None


@dataclass(frozen=True)
class InboundMessage:
    """One inbound user message for the pipeline; external ids are always ``str``."""

    external_message_id: str
    external_conversation_id: str
    inbox_ref: str
    contact_external_id: str
    contact_name: str | None
    contact_phone: str | None
    text: str
    attachments: tuple[InboundAttachment, ...] = ()
    sent_at: datetime | None = None


# Pydantic TypeAdapter: JSON round-trip for the debounce buffer (Redis strings).
_ADAPTER = TypeAdapter(InboundMessage)


def serialize_inbound(msg: InboundMessage) -> str:
    return _ADAPTER.dump_json(msg).decode()


def deserialize_inbound(raw: str) -> InboundMessage:
    return _ADAPTER.validate_json(raw)
