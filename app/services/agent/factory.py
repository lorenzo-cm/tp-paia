from functools import lru_cache

from app.core.config import get_settings
from app.services.agent import AnthropicAgent, BaseAgent, OpenAIAgent
from app.services.agent.exceptions import AgentError
from app.services.agent.prompts import SYSTEM_PROMPT_DEFAULT


@lru_cache(maxsize=1)
def get_agent() -> BaseAgent:
    settings = get_settings()
    if settings.AGENT_PROVIDER == "openai":
        if not settings.OPENAI_API_KEY:
            raise AgentError("OPENAI_API_KEY not configured")
        return OpenAIAgent(
            system_prompt=SYSTEM_PROMPT_DEFAULT,
            default_model="gpt-4o",
            default_temperature=1.0,
            api_key=settings.OPENAI_API_KEY,
        )
    elif settings.AGENT_PROVIDER == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise AgentError("ANTHROPIC_API_KEY not configured")
        return AnthropicAgent(
            system_prompt=SYSTEM_PROMPT_DEFAULT,
            default_model="claude-sonnet-4-5",
            default_temperature=1.0,
            api_key=settings.ANTHROPIC_API_KEY,
        )
    else:
        raise AgentError(f"Invalid agent provider: {settings.AGENT_PROVIDER}")
