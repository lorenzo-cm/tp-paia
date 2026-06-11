import pytest

from app.services.agent.base import AgentMessage, AgentResponse, BaseAgent


class _IncompleteAgent(BaseAgent):
    pass


class _RecordingAgent(BaseAgent):
    """Subclass that surfaces what defaults the base resolves on each call."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)  # type: ignore[arg-type]
        self.last_resolved: tuple[str, float] | None = None

    async def run(
        self,
        history: list[AgentMessage],
        user_message: AgentMessage,
        *,
        model: str | None = None,
        temperature: float | None = None,
    ) -> AgentResponse:
        resolved_model = model or self._default_model
        resolved_temp = (
            self._default_temperature if temperature is None else temperature
        )
        self.last_resolved = (resolved_model, resolved_temp)
        return AgentResponse(text="ok", model=resolved_model)


class TestBaseAgentContract:

    def test_base_agent_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            BaseAgent("system", "model")  # type: ignore[abstract]

    def test_subclass_without_run_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            _IncompleteAgent("system", "model")  # type: ignore[abstract]

    async def test_defaults_are_applied_when_run_called_without_overrides(self) -> None:
        agent = _RecordingAgent(
            system_prompt="sys", default_model="m-default", default_temperature=0.25
        )
        await agent.run([], AgentMessage(role="user", text="hi"))
        assert agent.last_resolved == ("m-default", 0.25)

    async def test_overrides_take_precedence_over_defaults(self) -> None:
        agent = _RecordingAgent(
            system_prompt="sys", default_model="m-default", default_temperature=0.25
        )
        await agent.run(
            [],
            AgentMessage(role="user", text="hi"),
            model="m-override",
            temperature=0.9,
        )
        assert agent.last_resolved == ("m-override", 0.9)
