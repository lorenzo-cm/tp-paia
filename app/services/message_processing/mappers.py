from typing import Literal

from app.db.models.conversations import Message, SenderType
from app.services.agent.base import AgentAttachment, AgentMessage


def _role_for(sender_type: SenderType) -> Literal["user", "assistant"] | None:
    if sender_type == SenderType.USER:
        return "user"
    if sender_type == SenderType.ASSISTANT:
        return "assistant"
    return None


def _agent_attachments_for(message: Message) -> list[AgentAttachment]:
    attachments: list[AgentAttachment] = []
    for att in message.attachments:
        mime = att.mime_type or ""
        if mime.startswith("image/"):
            attachments.append(
                AgentAttachment(file_type="image", mime_type=mime, url=att.url)
            )
        elif mime == "application/pdf":
            attachments.append(
                AgentAttachment(file_type="pdf", mime_type=mime, url=att.url)
            )
        # Other mimes carry no agent context — omitted.
    return attachments


def to_agent_messages(messages: list[Message]) -> list[AgentMessage]:
    """Map persisted ``Message`` rows to agent-history ``AgentMessage``s.

    Called by ``HistoryBuilder`` to build the prior-turns context.
    USER/ASSISTANT become user/assistant turns; SYSTEM/HUMAN and rows
    with no usable content are dropped (never crash the mapper). Pure:
    no DB/IO.
    """
    result: list[AgentMessage] = []
    for message in messages:
        role = _role_for(message.sender_type)
        if role is None:
            continue
        attachments = _agent_attachments_for(message)
        text = message.content or ""
        if not text and not attachments:
            continue
        result.append(AgentMessage(role=role, text=text, attachments=attachments))
    return result
