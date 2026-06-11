import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional

import sqlalchemy as sa
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .conversation_metric import ConversationMetric
    from .conversation_participant import ConversationParticipant
    from .message import Message


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConversationStatus(str, Enum):
    OPEN = "open"
    PENDING = "pending"
    RESOLVED = "resolved"


class ConversationBase(SQLModel):
    channel: str = "chatwoot"
    status: ConversationStatus = ConversationStatus.OPEN
    inbox_id: int = Field(index=True)
    external_conversation_id: int | None = Field(default=None, index=True)
    last_message_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )
    meta: dict[str, Any] | None = Field(
        default_factory=dict, sa_column=Column("metadata", JSON, nullable=True)
    )


class Conversation(ConversationBase, table=True):
    __tablename__ = "conversations"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )

    messages: list[Message] = Relationship(
        back_populates="conversation",
        cascade_delete=True,
    )
    participants: list[ConversationParticipant] = Relationship(
        back_populates="conversation",
        cascade_delete=True,
    )
    metric: Optional["ConversationMetric"] = Relationship(
        back_populates="conversation",
        sa_relationship_kwargs={"uselist": False},
    )


class ConversationCreate(ConversationBase):
    pass


class ConversationUpdate(SQLModel):
    id: uuid.UUID
    status: ConversationStatus | None = None
    last_message_at: datetime | None = None
    meta: dict[str, Any] | None = None
