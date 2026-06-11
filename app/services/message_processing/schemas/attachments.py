from dataclasses import dataclass
from typing import Literal

from app.services.agent.base import AgentAttachment


@dataclass(frozen=True)
class StoredAttachment:
    """Fetched bytes with mime, public URL, and file type."""

    data: bytes
    mime: str
    url: str
    file_type: Literal["image", "audio", "file"]


@dataclass
class ExtractResult:
    """Text for message content and/or an attachment for the multimodal agent."""

    text: str | None = None
    agent_attachment: AgentAttachment | None = None
