import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, relationship
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .conversation import Conversation
    from .conversation_participant import ConversationParticipant
    from .message_attachment import MessageAttachment


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SenderType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    HUMAN = "human"


class InteractionType(str, Enum):
    CHAT = "chat"
    TOOL_CALL = "tool_call"
    TOOL_RESPONSE = "tool_response"
    REASONING = "reasoning"


class MessageBase(SQLModel):
    conversation_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    sender_participant_id: uuid.UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("conversation_participants.id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
    sender_type: SenderType = Field(index=True)
    interaction_type: InteractionType = Field(default=InteractionType.CHAT, index=True)
    external_message_id: int | None = Field(default=None, index=True)
    content: str | None = None
    content_type: str = "text"
    sent_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False, index=True),
    )
    meta: dict[str, Any] | None = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=True)
    )


class Message(MessageBase, table=True):
    __tablename__ = "messages"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )

    conversation: Conversation = Relationship(back_populates="messages")
    sender_participant: Mapped[Optional["ConversationParticipant"]] = Relationship(
        sa_relationship=relationship(
            "ConversationParticipant",
            back_populates="messages_sent",
        )
    )
    attachments: list[MessageAttachment] = Relationship(
        back_populates="message",
        cascade_delete=True,
    )


class MessageCreate(MessageBase):
    pass


class MessageUpdate(SQLModel):
    id: uuid.UUID
    content: str | None = None
    meta: dict[str, Any] | None = None
