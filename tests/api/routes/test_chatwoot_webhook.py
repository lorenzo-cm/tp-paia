import asyncio
from typing import Any

from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.main import app
from app.services.chatwoot.factory import get_chatwoot_webhook_processor

_URL = f"{get_settings().API_PREFIX}/v1/webhook/chatwoot"


def _payload() -> dict[str, Any]:
    sender: dict[str, Any] = {
        "additional_attributes": {},
        "custom_attributes": {},
        "email": None,
        "id": 77,
        "identifier": None,
        "name": "Alice",
        "phone_number": "+551199",
        "thumbnail": "",
    }
    return {
        "account": {"id": 1, "name": "Acct"},
        "additional_attributes": {},
        "content_attributes": {},
        "content_type": "text",
        "content": "hi",
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
        "attachments": [],
    }


async def test_webhook_returns_200_and_schedules_processing() -> None:
    calls: list[Any] = []

    class FakeProcessor:
        async def process(self, webhook: Any) -> None:
            calls.append(webhook)

    app.dependency_overrides[get_chatwoot_webhook_processor] = lambda: FakeProcessor()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            resp = await ac.post(_URL, json=_payload())

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        await asyncio.sleep(0)
        assert len(calls) == 1
    finally:
        app.dependency_overrides.clear()


async def test_webhook_returns_immediately_without_awaiting_pipeline() -> None:
    started = asyncio.Event()
    release = asyncio.Event()
    finished: list[bool] = []

    class SlowProcessor:
        async def process(self, webhook: Any) -> None:
            started.set()
            await release.wait()
            finished.append(True)

    app.dependency_overrides[get_chatwoot_webhook_processor] = lambda: SlowProcessor()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://t") as ac:
            resp = await ac.post(_URL, json=_payload())

            assert resp.status_code == 200
            await asyncio.wait_for(started.wait(), timeout=1)
            assert finished == []
            release.set()
            await asyncio.sleep(0)
            assert finished == [True]
    finally:
        app.dependency_overrides.clear()
