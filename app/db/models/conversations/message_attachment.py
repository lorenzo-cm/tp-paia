import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .message import Message


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MessageAttachmentBase(SQLModel):
    message_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("messages.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
    )
    external_attachment_id: int | None = Field(default=None, index=True)
    url: str
    mime_type: str | None = None
    size_bytes: int | None = None
    extracted_text: str | None = None
    extract_type: str | None = None
    meta: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))


class MessageAttachment(MessageAttachmentBase, table=True):
    __tablename__ = "message_attachments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )

    message: Message = Relationship(back_populates="attachments")


class MessageAttachmentCreate(MessageAttachmentBase):
    pass


class MessageAttachmentUpdate(SQLModel):
    id: uuid.UUID
    url: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    extracted_text: str | None = None
    extract_type: str | None = None
    meta: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
