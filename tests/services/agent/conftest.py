from collections.abc import Callable
from typing import Any

import pytest

from app.services.agent.anthropic import AnthropicAgent
from app.services.agent.base import AgentAttachment, AgentMessage
from app.services.agent.openai import OpenAIAgent


def user_message(
    text: str = "hi", attachments: list[AgentAttachment] | None = None
) -> AgentMessage:
    return AgentMessage(role="user", text=text, attachments=attachments or [])


def assistant_message(text: str = "hello") -> AgentMessage:
    return AgentMessage(role="assistant", text=text)

# ---------------------------------------------------------------------------
# OpenAI fakes
# ---------------------------------------------------------------------------


class _FakeOpenAIContentBlock:
    def __init__(self, text: str, block_type: str = "output_text") -> None:
        self.text = text
        self.type = block_type


class _FakeOpenAIOutputItem:
    def __init__(
        self,
        content: list[_FakeOpenAIContentBlock] | None = None,
        *,
        item_type: str = "message",
        call_id: str | None = None,
        name: str | None = None,
        arguments: str | None = None,
        item_id: str | None = None,
    ) -> None:
        self.content = content
        self.type = item_type
        self.call_id = call_id
        self.name = name
        self.arguments = arguments
        self.id = item_id


class FakeOpenAIResponse:
    def __init__(
        self,
        *,
        output_text: str | None = "fake-openai-text",
        fallback_text: str | None = None,
        output: list[_FakeOpenAIOutputItem] | None = None,
        response_id: str | None = None,
    ) -> None:
        self.output_text = output_text
        self.id = response_id
        if output is not None:
            self.output = output
            return
        fallback = fallback_text if fallback_text is not None else "fallback-text"
        self.output = [
            _FakeOpenAIOutputItem(
                content=[_FakeOpenAIContentBlock(text=fallback)]
            )
        ]


class _FakeResponses:
    def __init__(self) -> None:
        self.last_call: dict[str, Any] | None = None
        self.calls: list[dict[str, Any]] = []
        self._next_response: FakeOpenAIResponse = FakeOpenAIResponse()
        self._responses_queue: list[FakeOpenAIResponse] = []
        self._raise: BaseException | None = None

    def set_response(self, response: FakeOpenAIResponse) -> None:
        self._next_response = response

    def set_responses(self, responses: list[FakeOpenAIResponse]) -> None:
        self._responses_queue = list(responses)

    def set_error(self, exc: BaseException) -> None:
        self._raise = exc

    async def create(self, **kwargs: Any) -> FakeOpenAIResponse:
        self.last_call = kwargs
        self.calls.append(kwargs)
        if self._raise is not None:
            raise self._raise
        if self._responses_queue:
            return self._responses_queue.pop(0)
        return self._next_response


class FakeAsyncOpenAI:
    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs: dict[str, Any] = kwargs
        self.responses = _FakeResponses()


# ---------------------------------------------------------------------------
# Anthropic fakes
# ---------------------------------------------------------------------------


class FakeAnthropicBlock:
    def __init__(self, text: str, block_type: str = "text") -> None:
        self.text = text
        self.type = block_type


class FakeAnthropicResponse:
    def __init__(self, blocks: list[FakeAnthropicBlock] | None = None) -> None:
        self.content = blocks if blocks is not None else [
            FakeAnthropicBlock(text="fake-anthropic-text")
        ]


class _FakeMessages:
    def __init__(self) -> None:
        self.last_call: dict[str, Any] | None = None
        self._next_response = FakeAnthropicResponse()
        self._raise: BaseException | None = None

    def set_response(self, response: FakeAnthropicResponse) -> None:
        self._next_response = response

    def set_error(self, exc: BaseException) -> None:
        self._raise = exc

    async def create(self, **kwargs: Any) -> FakeAnthropicResponse:
        self.last_call = kwargs
        if self._raise is not None:
            raise self._raise
        return self._next_response


class FakeAsyncAnthropic:
    def __init__(self, **kwargs: Any) -> None:
        self.init_kwargs: dict[str, Any] = kwargs
        self.messages = _FakeMessages()


# ---------------------------------------------------------------------------
# Settings helpers
# ---------------------------------------------------------------------------


def _clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "", raising=False)


def _clear_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "", raising=False)


def _set_openai_key(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", value, raising=False)


def _set_anthropic_key(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", value, raising=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clear_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_openai_key(monkeypatch)


@pytest.fixture
def clear_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_anthropic_key(monkeypatch)


@pytest.fixture
def set_openai_key(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    def _setter(value: str) -> None:
        _set_openai_key(monkeypatch, value)

    return _setter


@pytest.fixture
def set_anthropic_key(monkeypatch: pytest.MonkeyPatch) -> Callable[[str], None]:
    def _setter(value: str) -> None:
        _set_anthropic_key(monkeypatch, value)

    return _setter


@pytest.fixture
def openai_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[OpenAIAgent, FakeAsyncOpenAI]:
    fake = FakeAsyncOpenAI()

    def _factory(**kwargs: Any) -> FakeAsyncOpenAI:
        fake.init_kwargs = kwargs
        return fake

    monkeypatch.setattr("app.services.agent.openai.AsyncOpenAI", _factory)
    agent = OpenAIAgent(
        system_prompt="system-prompt",
        default_model="gpt-default",
        default_temperature=0.5,
        api_key="test-key",
    )
    return agent, fake


@pytest.fixture
def anthropic_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[AnthropicAgent, FakeAsyncAnthropic]:
    fake = FakeAsyncAnthropic()

    def _factory(**kwargs: Any) -> FakeAsyncAnthropic:
        fake.init_kwargs = kwargs
        return fake

    monkeypatch.setattr("app.services.agent.anthropic.AsyncAnthropic", _factory)
    agent = AnthropicAgent(
        system_prompt="system-prompt",
        default_model="claude-default",
        default_temperature=0.5,
        api_key="test-key",
    )
    return agent, fake


# ---------------------------------------------------------------------------
# SDK error builders
# ---------------------------------------------------------------------------


def make_openai_api_error(message: str = "boom") -> Exception:
    import httpx
    from openai import APIError

    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return APIError(message, request, body=None)


def make_anthropic_api_error(message: str = "boom") -> Exception:
    import httpx
    from anthropic import APIError

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return APIError(message, request, body=None)
