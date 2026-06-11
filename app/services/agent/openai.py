import json
from typing import Any

from openai import APIError, AsyncOpenAI

from app.services.agent.base import (
    AgentMessage,
    AgentResponse,
    AgentToolContext,
    BaseAgent,
)
from app.services.agent.exceptions import AgentError
from app.services.real_estate_tools import REAL_ESTATE_TOOLS


class OpenAIAgent(BaseAgent):
    """Multimodal agent backed by the OpenAI Responses API.

    Responses API is used instead of Chat Completions because it accepts PDFs by
    URL natively, avoiding base64 encoding and round-trips through the Files API.
    """

    def __init__(
        self,
        system_prompt: str,
        default_model: str,
        default_temperature: float = 1.0,
        *,
        api_key: str,
    ) -> None:
        if not api_key:
            raise AgentError("api_key is required")
        super().__init__(system_prompt, default_model, default_temperature)
        self._client = AsyncOpenAI(api_key=api_key)

    async def run(
        self,
        history: list[AgentMessage],
        user_message: AgentMessage,
        *,
        model: str | None = None,
        temperature: float | None = None,
        tool_context: AgentToolContext | None = None,
    ) -> AgentResponse:
        resolved_model = model or self._default_model
        resolved_temperature = (
            self._default_temperature if temperature is None else temperature
        )
        input_payload: list[dict[str, Any]] = self._build_messages(
            history, user_message
        )
        try:
            for _ in range(5):
                kwargs: dict[str, Any] = {
                    "model": resolved_model,
                    "instructions": self._system_prompt,
                    "input": input_payload,
                    "temperature": resolved_temperature,
                }
                if tool_context is not None:
                    kwargs["tools"] = REAL_ESTATE_TOOLS

                response = await self._client.responses.create(**kwargs)
                tool_calls = self._extract_tool_calls(response)
                if not tool_calls or tool_context is None:
                    return AgentResponse(
                        text=self._extract_text(response), model=resolved_model
                    )

                for call in tool_calls:
                    input_payload.append(
                        {
                            "type": "function_call",
                            "call_id": call["call_id"],
                            "name": call["name"],
                            "arguments": json.dumps(
                                call["arguments"], ensure_ascii=False, default=str
                            ),
                        }
                    )
                    result = await tool_context.execute_tool(
                        call["name"], call["arguments"]
                    )
                    input_payload.append(
                        {
                            "type": "function_call_output",
                            "call_id": call["call_id"],
                            "output": json.dumps(
                                result.output, ensure_ascii=False, default=str
                            ),
                        }
                    )
        except APIError as e:
            raise AgentError(f"OpenAI call failed: {e}") from e

        return AgentResponse(
            text=(
                "Nao consegui concluir a consulta automatica agora. "
                "Vou encaminhar para um atendente continuar o atendimento."
            ),
            model=resolved_model,
        )

    def _extract_text(self, response: Any) -> str:
        text = getattr(response, "output_text", None)
        if not text:
            output = getattr(response, "output", []) or []
            content = getattr(output[0], "content", []) if output else []
            text = "".join(
                b.text for b in content if getattr(b, "type", None) == "output_text"
            )
        return text or ""

    def _extract_tool_calls(self, response: Any) -> list[dict[str, Any]]:
        calls: list[dict[str, Any]] = []
        for item in getattr(response, "output", []) or []:
            if getattr(item, "type", None) != "function_call":
                continue
            raw_arguments = getattr(item, "arguments", "{}") or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError:
                arguments = {"_invalid_json": raw_arguments}
            calls.append(
                {
                    "call_id": getattr(item, "call_id", getattr(item, "id", "")),
                    "name": getattr(item, "name", ""),
                    "arguments": arguments,
                }
            )
        return calls

    def _build_messages(
        self, history: list[AgentMessage], user_message: AgentMessage
    ) -> list[dict[str, Any]]:
        return [
            *(self._build_history_message(message) for message in history),
            self._build_current_user_message(user_message),
        ]

    def _build_history_message(self, message: AgentMessage) -> dict[str, Any]:
        return {"role": message.role, "content": message.text}

    def _build_current_user_message(self, message: AgentMessage) -> dict[str, Any]:
        return {"role": message.role, "content": self._build_content_blocks(message)}

    def _build_content_blocks(self, message: AgentMessage) -> list[dict[str, Any]]:
        # Attachments before text: provider recommendation for both OpenAI and Anthropic.
        blocks: list[dict[str, Any]] = []
        for att in message.attachments:
            if att.file_type == "image":
                blocks.append({"type": "input_image", "image_url": att.url})
            elif att.file_type == "pdf":
                blocks.append({"type": "input_file", "file_url": att.url})
        if message.text:
            blocks.append({"type": "input_text", "text": message.text})
        return blocks
