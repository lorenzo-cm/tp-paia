import dataclasses
from datetime import datetime, timezone

import pytest

from app.services.message_processing.schemas import (
    InboundAttachment,
    InboundMessage,
    deserialize_inbound,
    serialize_inbound,
)


def test_inbound_message_is_frozen() -> None:
    msg = InboundMessage(
        external_message_id="1",
        external_conversation_id="2",
        inbox_ref="3",
        contact_external_id="4",
        contact_name="Alice",
        contact_phone="+5511999999999",
        text="hello",
    )

    with pytest.raises(dataclasses.FrozenInstanceError):
        msg.text = "mutated"  # type: ignore[misc]


def test_inbound_attachment_defaults() -> None:
    att = InboundAttachment(file_type="image", media_ref="ref-1")

    assert att.file_type == "image"
    assert att.media_ref == "ref-1"
    assert att.url is None
    assert att.filename is None
    assert att.mime_type is None
    assert att.size_bytes is None


def test_inbound_message_defaults_empty_attachments() -> None:
    msg = InboundMessage(
        external_message_id="1",
        external_conversation_id="2",
        inbox_ref="3",
        contact_external_id="4",
        contact_name=None,
        contact_phone=None,
        text="",
    )

    assert msg.attachments == ()
    assert msg.sent_at is None


def test_serialize_roundtrip() -> None:
    msg = InboundMessage(
        external_message_id="10",
        external_conversation_id="20",
        inbox_ref="30",
        contact_external_id="40",
        contact_name="Alice",
        contact_phone="+5511999999999",
        text="hello world",
        attachments=(
            InboundAttachment(
                file_type="image",
                media_ref="ref-1",
                url="https://cdn.test/a.png",
                filename="a.png",
                mime_type="image/png",
                size_bytes=123,
            ),
            InboundAttachment(file_type="audio", media_ref="ref-2"),
        ),
        sent_at=datetime(2026, 5, 19, 12, 30, 45, tzinfo=timezone.utc),
    )

    restored = deserialize_inbound(serialize_inbound(msg))

    assert restored == msg
    assert isinstance(restored.attachments, tuple)
    assert restored.sent_at == msg.sent_at
