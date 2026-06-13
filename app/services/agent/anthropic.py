from typing import Any

from anthropic import APIError, AsyncAnthropic

from app.services.agent.base import (
    AgentMessage,
    AgentResponse,
    AgentToolContext,
    BaseAgent,
)
from app.services.agent.exceptions import AgentError


class AnthropicAgent(BaseAgent):
    """Multimodal agent backed by the Anthropic Messages API.

    Supports text, images, and PDFs via public URLs (passed through as
    native ``image`` and ``document`` blocks; no base64 encoding required).
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
        self._client = AsyncAnthropic(api_key=api_key)

    async def run(
        self,
        history: list[AgentMessage],
        user_message: AgentMessage,
        *,
        model: str | None = None,
        temperature: float | None = None,
        tool_context: AgentToolContext | None = None,
    ) -> AgentResponse:
        if tool_context is not None:
            raise AgentError("AnthropicAgent does not support tool calling yet")
        model = model or self._default_model
        temperature = self._default_temperature if temperature is None else temperature
        try:
            response = await self._client.messages.create(
                model=model,
                system=self._system_prompt,
                max_tokens=64000,  # SDK requires the param;
                temperature=temperature,
                messages=self._build_messages(history, user_message),
            )
        except APIError as e:
            raise AgentError(f"Anthropic call failed: {e}") from e
        text = "".join(b.text for b in response.content if b.type == "text")
        return AgentResponse(text=text, model=model)

    def _build_messages(
        self, history: list[AgentMessage], user_message: AgentMessage
    ) -> list[dict[str, Any]]:
        return [
            {"role": m.role, "content": self._build_content(m)}
            for m in [*history, user_message]
        ]

    def _build_content(self, message: AgentMessage) -> list[dict[str, Any]]:
        # Attachments before text: Anthropic explicitly recommends this ordering for performance.
        blocks: list[dict[str, Any]] = []
        for att in message.attachments:
            if att.file_type == "image":
                blocks.append(
                    {"type": "image", "source": {"type": "url", "url": att.url}}
                )
            elif att.file_type == "pdf":
                blocks.append(
                    {"type": "document", "source": {"type": "url", "url": att.url}}
                )
        if message.text:
            blocks.append({"type": "text", "text": message.text})
        return blocks
