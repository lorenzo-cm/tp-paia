import asyncio
from contextlib import contextmanager
from unittest.mock import AsyncMock

import fakeredis
import pytest

from app.services.message_debouncer.service import MessageDebouncer


@pytest.fixture
def fake_redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def debouncer(fake_redis: fakeredis.FakeRedis) -> MessageDebouncer:
    @contextmanager
    def _factory():  # type: ignore
        yield fake_redis

    return MessageDebouncer(
        wait_time=100,
        max_attempts=3,
        max_messages=10,
        redis_factory=_factory,
    )


@pytest.fixture
def instant_sleep(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replaces asyncio.sleep with an AsyncMock that returns immediately without yielding."""
    mock = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", mock)
    return mock


@pytest.fixture
def yielding_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replaces asyncio.sleep with a version that yields to the event loop without waiting."""
    _real = asyncio.sleep

    async def _yield(_duration: float) -> None:
        await _real(0)

    monkeypatch.setattr(asyncio, "sleep", _yield)


class TestSingleCaller:
    async def test_returns_complete_debounce_info(
        self, debouncer: MessageDebouncer, instant_sleep: AsyncMock
    ) -> None:
        result = await debouncer.debounce("1", '{"content": "Hey"}')

        assert result is not None
        assert result.payloads == ['{"content": "Hey"}']
        assert result.attempts == 1


class TestMultipleCallers:
    async def test_subsequent_caller_returns_none(
        self, debouncer: MessageDebouncer, yielding_sleep: None
    ) -> None:
        task = asyncio.create_task(debouncer.debounce("1", "Hey"))
        await asyncio.sleep(0)  # yield so task can start and acquire the lock

        result = await debouncer.debounce("1", "What's up?")
        await task

        assert result is None

    async def test_all_burst_content_is_accumulated(
        self, debouncer: MessageDebouncer, yielding_sleep: None
    ) -> None:
        task = asyncio.create_task(debouncer.debounce("1", "Hey"))
        await asyncio.sleep(0)

        await debouncer.debounce("1", "What's up?")
        result = await task

        assert result is not None
        assert result.payloads == ["Hey", "What's up?"]
        assert result.attempts == 2

    async def test_conversation_reuse_starts_fresh(
        self,
        debouncer: MessageDebouncer,
        fake_redis: fakeredis.FakeRedis,
        instant_sleep: AsyncMock,
    ) -> None:
        result1 = await debouncer.debounce("1", "First burst")
        assert result1 is not None

        fake_redis.delete("conv:debounce:1")  # simulate the silence window having elapsed

        result2 = await debouncer.debounce("1", "Second burst")

        assert result2 is not None
        assert result2.payloads == ["Second burst"]


class TestSilenceWindowBehaviour:
    async def test_force_consumes_after_max_attempts_exhausted(
        self, debouncer: MessageDebouncer, instant_sleep: AsyncMock
    ) -> None:
        result = await debouncer.debounce("1", "Hey")

        assert result is not None
        assert instant_sleep.call_count == debouncer.max_attempts

    async def test_consumes_early_when_silence_window_expires(
        self,
        debouncer: MessageDebouncer,
        fake_redis: fakeredis.FakeRedis,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _real = asyncio.sleep
        call_count = 0

        async def sleep_then_expire(_duration: float) -> None:
            nonlocal call_count
            call_count += 1
            fake_redis.delete("conv:debounce:1")
            await _real(0)

        monkeypatch.setattr(asyncio, "sleep", sleep_then_expire)

        result = await debouncer.debounce("1", "Hey")

        assert call_count == 1  # exited loop early, did not exhaust max_attempts
        assert result is not None


class TestConversationIsolation:
    async def test_different_conversations_do_not_interfere(
        self, debouncer: MessageDebouncer, yielding_sleep: None
    ) -> None:
        task1 = asyncio.create_task(debouncer.debounce("1", "Conv 1 message"))
        task2 = asyncio.create_task(debouncer.debounce("2", "Conv 2 message"))

        result1, result2 = await asyncio.gather(task1, task2)

        assert result1 is not None
        assert result2 is not None
        assert result1.payloads == ["Conv 1 message"]
        assert result2.payloads == ["Conv 2 message"]


class TestCap:
    async def test_cap_keeps_most_recent_when_exceeding_max(
        self, debouncer: MessageDebouncer, yielding_sleep: None
    ) -> None:
        debouncer.max_messages = 5
        overflow = debouncer.max_messages + 2  # 7 payloads pushed

        task = asyncio.create_task(debouncer.debounce("1", "p0"))
        await asyncio.sleep(0)  # task acquires the lock and parks in the wait loop

        for i in range(1, overflow):
            none_result = await debouncer.debounce("1", f"p{i}")
            assert none_result is None  # subsequent callers only buffer

        result = await task

        assert result is not None
        # Exactly max_messages kept, the most recent ones, in arrival order.
        assert result.payloads == [f"p{i}" for i in range(overflow - debouncer.max_messages, overflow)]
        assert len(result.payloads) == debouncer.max_messages
