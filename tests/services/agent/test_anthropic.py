from collections.abc import Callable
from typing import Any

import pytest

from app.services.agent.anthropic import AnthropicAgent
from app.services.agent.base import (
    AgentAttachment,
    AgentMessage,
    AgentResponse,
)
from app.services.agent.exceptions import AgentError
from tests.services.agent.conftest import (
    FakeAnthropicBlock,
    FakeAnthropicResponse,
    FakeAsyncAnthropic,
    assistant_message,
    make_anthropic_api_error,
    user_message,
)


class TestAnthropicConstruction:

    def test_raises_when_api_key_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.agent.anthropic.AsyncAnthropic",
            lambda **kw: FakeAsyncAnthropic(**kw),
        )
        with pytest.raises(AgentError):
            AnthropicAgent(system_prompt="s", default_model="m", api_key="")

    def test_accepts_constructor_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def _factory(**kwargs: Any) -> FakeAsyncAnthropic:
            captured.update(kwargs)
            return FakeAsyncAnthropic(**kwargs)

        monkeypatch.setattr("app.services.agent.anthropic.AsyncAnthropic", _factory)
        AnthropicAgent(system_prompt="s", default_model="m", api_key="from-arg")
        assert captured["api_key"] == "from-arg"


class TestAnthropicRun:

    async def test_returns_agent_response_with_text_and_model(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        fake.messages.set_response(
            FakeAnthropicResponse([FakeAnthropicBlock(text="hello world")])
        )
        result = await agent.run([], user_message("hi"))
        assert isinstance(result, AgentResponse)
        assert result.text == "hello world"
        assert result.model == "claude-default"

    async def test_returns_only_text_content_when_response_mixes_block_types(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        fake.messages.set_response(
            FakeAnthropicResponse(
                [
                    FakeAnthropicBlock(text="alpha"),
                    FakeAnthropicBlock(text="ignored", block_type="tool_use"),
                    FakeAnthropicBlock(text="beta"),
                ]
            )
        )
        result = await agent.run([], user_message("hi"))
        assert "alpha" in result.text and "beta" in result.text
        assert "ignored" not in result.text

    async def test_default_model_is_used_when_override_is_none(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        await agent.run([], user_message("hi"))
        assert fake.messages.last_call is not None
        assert fake.messages.last_call["model"] == "claude-default"

    async def test_model_override_propagates_to_sdk(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        await agent.run([], user_message("hi"), model="claude-override")
        assert fake.messages.last_call is not None
        assert fake.messages.last_call["model"] == "claude-override"

    async def test_temperature_override_propagates_to_sdk(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        await agent.run([], user_message("hi"), temperature=0.9)
        assert fake.messages.last_call is not None
        assert fake.messages.last_call["temperature"] == 0.9

    async def test_system_prompt_sent_via_system_kwarg(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        await agent.run([], user_message("hi"))
        assert fake.messages.last_call is not None
        assert fake.messages.last_call["system"] == "system-prompt"

    async def test_conversation_chronological_order_is_preserved(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        await agent.run(
            [user_message("first"), assistant_message("second")],
            user_message("third"),
        )
        assert fake.messages.last_call is not None
        roles = [m["role"] for m in fake.messages.last_call["messages"]]
        assert roles == ["user", "assistant", "user"]

    async def test_text_only_message_succeeds(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, _ = anthropic_agent
        result = await agent.run([], user_message("just text"))
        assert isinstance(result, AgentResponse)

    async def test_each_attachment_url_reaches_sdk(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        urls = ["https://x/a.png", "https://x/b.png", "https://x/c.pdf"]
        msg = user_message(
            "look",
            attachments=[
                AgentAttachment(file_type="image", mime_type="image/png", url=urls[0]),
                AgentAttachment(file_type="image", mime_type="image/png", url=urls[1]),
                AgentAttachment(file_type="pdf", mime_type="application/pdf", url=urls[2]),
            ],
        )
        await agent.run([], msg)
        assert fake.messages.last_call is not None
        sent_repr = repr(fake.messages.last_call["messages"])
        for url in urls:
            assert url in sent_repr


class TestAnthropicShape:

    async def test_user_message_block_shape_is_exact(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        msg = AgentMessage(
            role="user",
            text="describe these",
            attachments=[
                AgentAttachment(
                    file_type="image",
                    mime_type="image/png",
                    url="https://example.com/img.png",
                ),
                AgentAttachment(
                    file_type="pdf",
                    mime_type="application/pdf",
                    url="https://example.com/doc.pdf",
                ),
            ],
        )
        await agent.run([], msg)
        assert fake.messages.last_call is not None
        sent = fake.messages.last_call["messages"]
        assert sent == [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "url", "url": "https://example.com/img.png"},
                    },
                    {
                        "type": "document",
                        "source": {"type": "url", "url": "https://example.com/doc.pdf"},
                    },
                    {"type": "text", "text": "describe these"},
                ],
            }
        ]


class TestAnthropicErrorHandling:

    async def test_apierror_is_wrapped_in_agent_error(
        self, anthropic_agent: tuple[AnthropicAgent, FakeAsyncAnthropic]
    ) -> None:
        agent, fake = anthropic_agent
        original = make_anthropic_api_error("upstream failed")
        fake.messages.set_error(original)
        with pytest.raises(AgentError) as exc_info:
            await agent.run([], user_message("hi"))
        assert exc_info.value.__cause__ is original
