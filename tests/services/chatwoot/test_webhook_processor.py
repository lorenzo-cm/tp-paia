"""ChatwootWebhookProcessor tests."""

import logging
from typing import Any

import pytest

from app.services.chatwoot.media_fetcher import ChatwootMediaFetcher
from app.services.chatwoot.schemas.webhook import ChatwootWebhook
from app.services.chatwoot.webhook_processor import ChatwootWebhookProcessor
from app.services.message_processing.schemas import InboundMessage


def _sender_dict() -> dict[str, Any]:
    return {
        "additional_attributes": {},
        "custom_attributes": {},
        "email": None,
        "id": 77,
        "identifier": None,
        "name": "Alice",
        "phone_number": "+551199",
        "thumbnail": "",
    }


def _webhook(*, message_type: str = "incoming", content: str = "hi") -> ChatwootWebhook:
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
        "message_type": message_type,
        "private": False,
        "sender": sender,
        "source_id": None,
        "event": "message_created",
        "attachments": [],
    }
    return ChatwootWebhook.model_validate(payload)


class FakePipeline:
    def __init__(self, *, raises: bool = False) -> None:
        self.calls: list[Any] = []
        self._raises = raises

    async def process(self, msg: Any, sender: Any, media_fetcher: Any) -> None:
        self.calls.append(msg)
        if self._raises:
            raise RuntimeError("boom")


def _processor(pipeline: Any) -> ChatwootWebhookProcessor:
    return ChatwootWebhookProcessor(
        pipeline, sender=object(), media_fetcher=ChatwootMediaFetcher()
    )


async def test_non_incoming_is_ignored() -> None:
    pipeline = FakePipeline()

    await _processor(pipeline).process(_webhook(message_type="outgoing"))

    assert pipeline.calls == []


async def test_parses_and_calls_pipeline_with_inbound_message() -> None:
    webhook = _webhook(content="hello there")
    pipeline = FakePipeline()

    await _processor(pipeline).process(webhook)

    assert len(pipeline.calls) == 1
    dto = pipeline.calls[0]
    assert isinstance(dto, InboundMessage)
    assert dto.external_message_id == str(webhook.id)
    assert dto.text == "hello there"


async def test_exception_is_logged_not_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    webhook = _webhook()
    pipeline = FakePipeline(raises=True)

    with caplog.at_level(logging.ERROR):
        await _processor(pipeline).process(webhook)

    assert "chatwoot webhook processing failed" in caplog.text
