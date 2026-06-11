from typing import Any

from app.services.chatwoot.schemas.webhook import ChatwootWebhook
from app.services.chatwoot.webhook_mapper import map_webhook_to_inbound


def _sender_dict() -> dict[str, Any]:
    return {
        "additional_attributes": {},
        "custom_attributes": {},
        "email": None,
        "id": 77,
        "identifier": None,
        "name": "Alice",
        "phone_number": "+5511999999999",
        "thumbnail": "",
    }


def _webhook(
    *,
    content: str | None = "hello",
    attachments: list[dict[str, Any]] | None = None,
) -> ChatwootWebhook:
    sender = _sender_dict()
    payload: dict[str, Any] = {
        "account": {"id": 1, "name": "Acct"},
        "additional_attributes": {},
        "content_attributes": {},
        "content_type": "text",
        "content": content,
        "conversation": {
            "additional_attributes": {},
            "can_reply": True,
            "channel": "Channel::Api",
            "contact_inbox": {
                "id": 10,
                "contact_id": 77,
                "inbox_id": 5,
                "source_id": None,
                "created_at": "2026-05-18T00:00:00Z",
                "updated_at": "2026-05-18T00:00:00Z",
                "hmac_verified": False,
                "pubsub_token": "tok",
            },
            "id": 42,
            "inbox_id": 5,
            "messages": [],
            "labels": [],
            "meta": {
                "sender": sender,
                "assignee": None,
                "team": None,
                "hmac_verified": False,
            },
            "status": "open",
            "custom_attributes": {},
            "snoozed_until": None,
            "unread_count": 1,
            "first_reply_created_at": None,
            "priority": None,
            "waiting_since": 0,
            "agent_last_seen_at": 0,
            "contact_last_seen_at": 0,
            "last_activity_at": 0,
            "timestamp": 0,
            "created_at": 0,
        },
        "created_at": "2026-05-18T00:00:00Z",
        "id": 123,
        "inbox": {"id": 5, "name": "Inbox"},
        "message_type": "incoming",
        "private": False,
        "sender": sender,
        "source_id": None,
        "event": "message_created",
        "attachments": attachments or [],
    }
    return ChatwootWebhook.model_validate(payload)


def test_maps_core_fields() -> None:
    msg = map_webhook_to_inbound(_webhook())

    assert msg.external_message_id == "123"
    assert msg.external_conversation_id == "42"
    assert msg.inbox_ref == "5"
    assert msg.contact_external_id == "77"
    assert msg.contact_name == "Alice"
    assert msg.contact_phone == "+5511999999999"
    assert msg.text == "hello"
    assert all(
        isinstance(v, str)
        for v in (
            msg.external_message_id,
            msg.external_conversation_id,
            msg.inbox_ref,
            msg.contact_external_id,
        )
    )


def test_maps_attachments() -> None:
    msg = map_webhook_to_inbound(
        _webhook(
            attachments=[
                {
                    "id": 1,
                    "message_id": 123,
                    "file_type": "image",
                    "account_id": 1,
                    "data_url": "https://cw.example/files/photo.png",
                    "file_size": 2048,
                },
                {
                    "id": 2,
                    "message_id": 123,
                    "file_type": "file",
                    "account_id": 1,
                    "data_url": "https://cw.example/files/doc.pdf",
                    "file_size": 4096,
                },
            ]
        )
    )

    assert len(msg.attachments) == 2
    image, file = msg.attachments

    assert image.file_type == "image"
    assert image.media_ref == "https://cw.example/files/photo.png"
    assert image.url == "https://cw.example/files/photo.png"
    assert image.filename == "photo.png"
    assert image.mime_type is None
    assert image.size_bytes == 2048

    assert file.file_type == "file"
    assert file.size_bytes == 4096


def test_video_attachment_is_mapped_to_file() -> None:
    msg = map_webhook_to_inbound(
        _webhook(
            attachments=[
                {
                    "id": 3,
                    "message_id": 123,
                    "file_type": "video",
                    "account_id": 1,
                    "data_url": "https://cw.example/files/clip.mp4",
                    "file_size": 8192,
                }
            ]
        )
    )

    assert msg.attachments[0].file_type == "file"


def test_content_none_becomes_empty_string() -> None:
    msg = map_webhook_to_inbound(_webhook(content=None))

    assert msg.text == ""


def test_no_attachments_yields_empty_tuple() -> None:
    msg = map_webhook_to_inbound(_webhook())

    assert msg.attachments == ()
