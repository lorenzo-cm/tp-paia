import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlmodel import JSON, Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .conversation import Conversation


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LeadQuality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FinalOutcome(str, Enum):
    RETAINED = "retained"
    HANDOFF = "handoff"
    DROPPED = "dropped"


def enum_values(enum_class: type[Enum]) -> list[str]:
    return [str(member.value) for member in enum_class]


class ConversationMetricBase(SQLModel):
    conversation_id: uuid.UUID = Field(
        sa_column=sa.Column(
            sa.Uuid,
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
    )
    lead_quality: LeadQuality | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Enum(
                LeadQuality,
                values_callable=enum_values,
                native_enum=False,
                create_constraint=False,
                length=6,
            ),
            nullable=True,
            index=True,
        ),
    )
    qualification_reason: str | None = Field(default=None, max_length=255)
    final_outcome: FinalOutcome | None = Field(
        default=None,
        sa_column=sa.Column(
            sa.Enum(
                FinalOutcome,
                values_callable=enum_values,
                native_enum=False,
                create_constraint=False,
                length=8,
            ),
            nullable=True,
            index=True,
        ),
    )
    used_human_transfer: bool = False
    response_time_min_ms: int | None = None
    response_time_max_ms: int | None = None
    response_time_count: int = 0
    tool_usage: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSON, nullable=False),
    )
    closed_at: datetime | None = Field(
        default=None,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=True),
    )


class ConversationMetric(ConversationMetricBase, table=True):
    __tablename__ = "conversation_metrics"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )

    conversation: "Conversation" = Relationship(back_populates="metric")


class ConversationMetricCreate(ConversationMetricBase):
    pass


class ConversationMetricUpdate(SQLModel):
    id: uuid.UUID
    lead_quality: LeadQuality | None = None
    qualification_reason: str | None = None
    final_outcome: FinalOutcome | None = None
    used_human_transfer: bool | None = None
    response_time_min_ms: int | None = None
    response_time_max_ms: int | None = None
    response_time_count: int | None = None
    tool_usage: dict[str, Any] | None = None
    updated_at: datetime | None = None
    closed_at: datetime | None = None
