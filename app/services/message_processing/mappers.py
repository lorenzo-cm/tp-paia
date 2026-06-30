from typing import Literal

from app.db.models.conversations import InteractionType, Message, SenderType
from app.services.agent.base import AgentAttachment, AgentMessage

MEDIA_SEND_TOOLS = {"send_photo_file", "send_video_file", "send_building_document"}


def _role_for(sender_type: SenderType) -> Literal["user", "assistant"] | None:
    if sender_type == SenderType.USER:
        return "user"
    if sender_type == SenderType.ASSISTANT:
        return "assistant"
    return None


def _media_already_sent_note(message: Message) -> str | None:
    """Turn a successful media-send tool response into a short assistant note so
    the model knows, across turns, which files it has already delivered.

    Returns ``None`` for any message that is not a successful media send.
    """
    if message.interaction_type != InteractionType.TOOL_RESPONSE:
        return None
    meta = message.meta or {}
    if meta.get("event") != "tool_success":
        return None
    if meta.get("tool_name") not in MEDIA_SEND_TOOLS:
        return None
    names = [
        str(url).rstrip("/").split("/")[-1]
        for url in meta.get("media_urls") or []
        if url
    ]
    if not names:
        return None
    return f"[midia ja enviada ao cliente: {', '.join(names)}]"


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
    USER/ASSISTANT become user/assistant turns; successful media-send tool
    responses become a short assistant note so the model knows what it already
    delivered; other SYSTEM/HUMAN rows and rows with no usable content are
    dropped (never crash the mapper). Pure: no DB/IO.
    """
    result: list[AgentMessage] = []
    for message in messages:
        media_note = _media_already_sent_note(message)
        if media_note is not None:
            result.append(AgentMessage(role="assistant", text=media_note))
            continue
        role = _role_for(message.sender_type)
        if role is None:
            continue
        attachments = _agent_attachments_for(message)
        text = message.content or ""
        if not text and not attachments:
            continue
        result.append(AgentMessage(role=role, text=text, attachments=attachments))
    return result
