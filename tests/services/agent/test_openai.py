from typing import Any

import pytest

from app.services.agent.base import (
    AgentAttachment,
    AgentMessage,
    AgentResponse,
    AgentToolContext,
    ToolResult,
)
from app.services.agent.exceptions import AgentError
from app.services.agent.openai import OpenAIAgent
from tests.services.agent.conftest import (
    FakeAsyncOpenAI,
    FakeOpenAIResponse,
    _FakeOpenAIOutputItem,
    assistant_message,
    make_openai_api_error,
    user_message,
)


class TestOpenAIConstruction:

    def test_raises_when_api_key_is_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.agent.openai.AsyncOpenAI", lambda **kw: FakeAsyncOpenAI(**kw)
        )
        with pytest.raises(AgentError):
            OpenAIAgent(system_prompt="s", default_model="m", api_key="")

    def test_accepts_constructor_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, Any] = {}

        def _factory(**kwargs: Any) -> FakeAsyncOpenAI:
            captured.update(kwargs)
            return FakeAsyncOpenAI(**kwargs)

        monkeypatch.setattr("app.services.agent.openai.AsyncOpenAI", _factory)
        OpenAIAgent(system_prompt="s", default_model="m", api_key="from-arg")
        assert captured["api_key"] == "from-arg"


class TestOpenAIRun:

    async def test_returns_agent_response_with_text_and_model(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        fake.responses.set_response(FakeOpenAIResponse(output_text="hello world"))
        result = await agent.run([], user_message("hi"))
        assert isinstance(result, AgentResponse)
        assert result.text == "hello world"
        assert result.model == "gpt-default"

    async def test_default_model_is_used_when_override_is_none(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        await agent.run([], user_message("hi"))
        assert fake.responses.last_call is not None
        assert fake.responses.last_call["model"] == "gpt-default"

    async def test_model_override_propagates_to_sdk(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        await agent.run([], user_message("hi"), model="gpt-override")
        assert fake.responses.last_call is not None
        assert fake.responses.last_call["model"] == "gpt-override"

    async def test_temperature_override_propagates_to_sdk(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        await agent.run([], user_message("hi"), temperature=0.9)
        assert fake.responses.last_call is not None
        assert fake.responses.last_call["temperature"] == 0.9

    async def test_system_prompt_sent_via_instructions_kwarg(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        await agent.run([], user_message("hi"))
        assert fake.responses.last_call is not None
        assert fake.responses.last_call["instructions"] == "system-prompt"

    async def test_conversation_chronological_order_is_preserved(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        await agent.run(
            [user_message("first"), assistant_message("second")],
            user_message("third"),
        )
        assert fake.responses.last_call is not None
        roles = [m["role"] for m in fake.responses.last_call["input"]]
        assert roles == ["user", "assistant", "user"]

    async def test_history_messages_are_sent_as_plain_text_content(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        await agent.run(
            [user_message("first"), assistant_message("second")],
            user_message("third"),
        )
        assert fake.responses.last_call is not None
        sent = fake.responses.last_call["input"]
        assert sent[0] == {"role": "user", "content": "first"}
        assert sent[1] == {"role": "assistant", "content": "second"}
        assert sent[2] == {
            "role": "user",
            "content": [{"type": "input_text", "text": "third"}],
        }

    async def test_text_only_message_succeeds(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, _ = openai_agent
        result = await agent.run([], user_message("just text"))
        assert isinstance(result, AgentResponse)

    async def test_each_attachment_url_reaches_sdk(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
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
        assert fake.responses.last_call is not None
        sent_repr = repr(fake.responses.last_call["input"])
        for url in urls:
            assert url in sent_repr

    async def test_returns_text_when_sdk_response_uses_alternate_payload_path(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        fake.responses.set_response(
            FakeOpenAIResponse(output_text=None, fallback_text="rescued-text")
        )
        result = await agent.run([], user_message("hi"))
        assert result.text == "rescued-text"


class TestOpenAIShape:

    async def test_user_message_block_shape_is_exact(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
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
        assert fake.responses.last_call is not None
        sent = fake.responses.last_call["input"]
        assert sent == [
            {
                "role": "user",
                "content": [
                    {"type": "input_image", "image_url": "https://example.com/img.png"},
                    {"type": "input_file", "file_url": "https://example.com/doc.pdf"},
                    {"type": "input_text", "text": "describe these"},
                ],
            }
        ]

    async def test_historical_assistant_message_does_not_use_input_text_blocks(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        await agent.run(
            [assistant_message("historico do assistente")],
            user_message("nova pergunta"),
        )
        assert fake.responses.last_call is not None
        sent = fake.responses.last_call["input"]
        assert sent[0] == {
            "role": "assistant",
            "content": "historico do assistente",
        }
        assert "input_text" not in repr(sent[0])


class TestOpenAITools:

    async def test_tool_call_loop_appends_function_call_and_output(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        fake.responses.set_responses(
            [
                FakeOpenAIResponse(
                    output_text="",
                    output=[
                        _FakeOpenAIOutputItem(
                            content=[],
                            item_type="function_call",
                            call_id="call_123",
                            name="search_building_information",
                            arguments='{"building_id": 42}',
                        )
                    ],
                ),
                FakeOpenAIResponse(output_text="resultado final"),
            ]
        )

        async def _execute_tool(name: str, arguments: dict[str, Any]) -> ToolResult:
            assert name == "search_building_information"
            assert arguments == {"building_id": 42}
            return ToolResult(output={"success": True, "tool_output": {"id": 42}})

        result = await agent.run(
            [assistant_message("contexto")],
            user_message("quero detalhes"),
            tool_context=AgentToolContext(execute_tool=_execute_tool),
        )

        assert result.text == "resultado final"
        assert len(fake.responses.calls) == 2
        first_call = fake.responses.calls[0]
        second_call = fake.responses.calls[1]
        assert first_call["input"][0] == {"role": "assistant", "content": "contexto"}
        assert second_call["input"][-2] == {
            "type": "function_call",
            "call_id": "call_123",
            "name": "search_building_information",
            "arguments": '{"building_id": 42}',
        }
        assert second_call["input"][-1] == {
            "type": "function_call_output",
            "call_id": "call_123",
            "output": '{"success": true, "tool_output": {"id": 42}}',
        }
        assert "previous_response_id" not in first_call
        assert "previous_response_id" not in second_call

    async def test_stops_after_five_tool_iterations(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        fake.responses.set_responses(
            [
                FakeOpenAIResponse(
                    output_text="",
                    output=[
                        _FakeOpenAIOutputItem(
                            content=[],
                            item_type="function_call",
                            call_id=f"call_{index}",
                            name="search_building_information",
                            arguments='{"building_id": 1}',
                        )
                    ],
                )
                for index in range(6)
            ]
        )

        async def _execute_tool(_: str, __: dict[str, Any]) -> ToolResult:
            return ToolResult(output={"success": True})

        result = await agent.run(
            [],
            user_message("teste"),
            tool_context=AgentToolContext(execute_tool=_execute_tool),
        )

        assert len(fake.responses.calls) == 5
        assert "Nao consegui concluir" in result.text


class TestOpenAIErrorHandling:

    async def test_apierror_is_wrapped_in_agent_error(
        self, openai_agent: tuple[OpenAIAgent, FakeAsyncOpenAI]
    ) -> None:
        agent, fake = openai_agent
        original = make_openai_api_error("upstream failed")
        fake.responses.set_error(original)
        with pytest.raises(AgentError) as exc_info:
            await agent.run([], user_message("hi"))
        assert exc_info.value.__cause__ is original
