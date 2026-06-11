from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AgentAttachment:
    file_type: Literal["image", "pdf"]
    mime_type: str
    url: str
    bytes: bytes | None = None


@dataclass
class AgentMessage:
    role: Literal["user", "assistant"]
    text: str
    attachments: list[AgentAttachment] = field(default_factory=list)


@dataclass
class AgentResponse:
    text: str
    model: str


@dataclass
class ToolResult:
    output: dict[str, Any]
    media_urls: list[str] = field(default_factory=list)


ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[ToolResult]]


@dataclass
class AgentToolContext:
    execute_tool: ToolExecutor


class BaseAgent(ABC):
    def __init__(
        self,
        system_prompt: str,
        default_model: str,
        default_temperature: float = 1.0,
    ) -> None:
        self._system_prompt = system_prompt
        self._default_model = default_model
        self._default_temperature = default_temperature

    @abstractmethod
    async def run(
        self,
        history: list[AgentMessage],
        user_message: AgentMessage,
        *,
        model: str | None = None,
        temperature: float | None = None,
        tool_context: AgentToolContext | None = None,
    ) -> AgentResponse: ...

    async def decline_unsafe_input(self) -> AgentResponse:
        """Reply when moderation blocked the user's message (LLM, not a canned line)."""
        return await self.run(
            [],
            AgentMessage(
                role="user",
                text=(
                    "A mensagem do usuário foi bloqueada pela moderação de conteúdo. "
                    "Responda em português do Brasil: recuse educadamente, de forma breve "
                    "e natural. Não reproduza, cite nem descreva o conteúdo bloqueado."
                ),
            ),
            temperature=0.7,
        )
