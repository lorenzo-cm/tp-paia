import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .conversation_participant import ConversationParticipant


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ContactBase(SQLModel):
    external_contact_id: int | None = Field(default=None, index=True)
    name: str | None = None
    phone: str | None = None
    email: str | None = None


class Contact(ContactBase, table=True):
    __tablename__ = "contacts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )

    participations: list[ConversationParticipant] = Relationship(
        back_populates="contact"
    )


class ContactCreate(ContactBase):
    pass


class ContactUpdate(SQLModel):
    id: uuid.UUID
    name: str | None = None
    phone: str | None = None
    email: str | None = None
