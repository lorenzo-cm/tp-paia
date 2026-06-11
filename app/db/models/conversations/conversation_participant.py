import uuid
from enum import Enum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.db.models.conversations.contact import Contact
    from app.db.models.conversations.conversation import Conversation
    from app.db.models.conversations.message import Message


class ParticipantType(str, Enum):
    CONTACT = "contact"
    AGENT = "agent"
    BOT = "bot"


class ConversationParticipantBase(SQLModel):
    conversation_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    participant_type: ParticipantType = Field(index=True)
    contact_id: uuid.UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    agent_user_id: uuid.UUID | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


class ConversationParticipant(ConversationParticipantBase, table=True):
    __tablename__ = "conversation_participants"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)

    conversation: Conversation = Relationship(back_populates="participants")
    contact: Contact = Relationship(back_populates="participations")
    messages_sent: list[Message] = Relationship(back_populates="sender_participant")


class ConversationParticipantCreate(ConversationParticipantBase):
    pass


class ConversationParticipantUpdate(SQLModel):
    id: uuid.UUID
    contact_id: uuid.UUID | None = None
    agent_user_id: uuid.UUID | None = None
