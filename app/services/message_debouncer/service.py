import asyncio
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.services.storage.redis_client import get_redis_client


class DebounceInfo(BaseModel):
    """
    Information about the debounce.

    `payloads` are opaque strings (the channel decides their shape); the
    debouncer never inspects them.
    """

    payloads: list[str]
    attempts: int


class MessageDebouncer:
    """
    Service for debouncing messages.

    It accumulates opaque payloads received for a conversation so they can be
    handled at once. The conversation id is a `str` (covers Chatwoot numeric
    ids and WhatsApp string ids alike).
    """

    def __init__(
        self,
        *,
        wait_time: int,
        max_attempts: int,
        max_messages: int,
        redis_factory: Callable[..., Any] = get_redis_client,
    ) -> None:
        self.wait_time: int = wait_time
        self.max_attempts: int = max_attempts
        self.max_messages: int = max_messages
        self._redis = redis_factory

    def _keys(self, conversation_id: str) -> dict[str, str]:
        return {
            "debounce": f"conv:debounce:{conversation_id}",
            "payloads": f"conv:payloads:{conversation_id}",
            "attempts": f"conv:attempts:{conversation_id}",
        }

    async def debounce(
        self, conversation_id: str, payload: str
    ) -> DebounceInfo | None:
        keys = self._keys(conversation_id)
        safety_ttl_ms = self.wait_time * self.max_attempts * 2

        with self._redis() as r:
            pipe = r.pipeline()
            pipe.rpush(keys["payloads"], payload)
            pipe.incr(keys["attempts"])
            pipe.pexpire(keys["payloads"], safety_ttl_ms)
            pipe.pexpire(keys["attempts"], safety_ttl_ms)
            pipe.set(keys["debounce"], 1, px=self.wait_time, nx=True)
            *_, acquired = pipe.execute()

        # If many messages arrive, only the first thread will acquire the lock
        # and then process all messages at once.
        if not acquired:
            with self._redis() as r:
                r.pexpire(keys["debounce"], self.wait_time)
            return None

        return await self._debounce_wait_loop(conversation_id)

    async def _debounce_wait_loop(self, conversation_id: str) -> DebounceInfo | None:
        keys = self._keys(conversation_id)
        for _ in range(self.max_attempts):
            await asyncio.sleep(self.wait_time / 1000)
            with self._redis() as r:
                if not r.exists(keys["debounce"]):
                    break
        return self._consume(conversation_id)

    def _consume(self, conversation_id: str) -> DebounceInfo | None:
        keys = self._keys(conversation_id)
        with self._redis() as r:
            pipe = r.pipeline()
            # Cap: keep the `max_messages` most recent payloads, discarding the
            # older overflow. "Most recent" is the deliberate choice — under a
            # flood the latest user intent matters more than stale early noise.
            pipe.lrange(keys["payloads"], -self.max_messages, -1)
            pipe.get(keys["attempts"])
            pipe.delete(keys["payloads"], keys["attempts"])
            payloads, attempts, _ = pipe.execute()

        if not payloads:
            return None
        return DebounceInfo(
            payloads=payloads,
            attempts=int(attempts or 0),
        )
