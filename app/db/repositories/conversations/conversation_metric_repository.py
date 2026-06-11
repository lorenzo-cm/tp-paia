from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from app.db.models.conversations import (
    Conversation,
    ConversationMetric,
    ConversationMetricCreate,
    FinalOutcome,
    LeadQuality,
)
from app.db.repositories.base import BaseRepository


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ConversationMetricRepository(
    BaseRepository[ConversationMetric, ConversationMetricCreate, ConversationMetric, UUID]
):
    def __init__(self, db: Session):
        super().__init__(db, ConversationMetric)

    def get_by_conversation_id(self, conversation_id: UUID) -> ConversationMetric | None:
        statement = select(ConversationMetric).where(
            ConversationMetric.conversation_id == conversation_id
        )
        return self.db.exec(statement).first()

    def get_or_create_by_conversation_id(self, conversation_id: UUID) -> ConversationMetric:
        existing = self.get_by_conversation_id(conversation_id)
        if existing is not None:
            return existing
        return self.create(ConversationMetricCreate(conversation_id=conversation_id))

    def update_lead_quality(
        self,
        conversation_id: UUID,
        lead_quality: LeadQuality | None,
        qualification_reason: str | None,
    ) -> ConversationMetric:
        metric = self.get_or_create_by_conversation_id(conversation_id)
        metric.lead_quality = lead_quality
        metric.qualification_reason = qualification_reason.strip() if qualification_reason else None
        metric.updated_at = utc_now()
        self.db.add(metric)
        self.db.flush()
        self.db.refresh(metric)
        return metric

    def increment_tool_usage(self, conversation_id: UUID, tool_name: str) -> ConversationMetric:
        metric = self.get_or_create_by_conversation_id(conversation_id)
        usage = dict(metric.tool_usage or {})
        usage[tool_name] = int(usage.get(tool_name, 0)) + 1
        metric.tool_usage = usage
        metric.updated_at = utc_now()
        self.db.add(metric)
        self.db.flush()
        self.db.refresh(metric)
        return metric

    def record_response_time(self, conversation_id: UUID, response_time_ms: int) -> ConversationMetric:
        metric = self.get_or_create_by_conversation_id(conversation_id)
        metric.response_time_min_ms = (
            response_time_ms
            if metric.response_time_min_ms is None
            else min(metric.response_time_min_ms, response_time_ms)
        )
        metric.response_time_max_ms = (
            response_time_ms
            if metric.response_time_max_ms is None
            else max(metric.response_time_max_ms, response_time_ms)
        )
        metric.response_time_count += 1
        metric.updated_at = utc_now()
        self.db.add(metric)
        self.db.flush()
        self.db.refresh(metric)
        return metric

    def mark_handoff(
        self,
        conversation_id: UUID,
        *,
        lead_quality: LeadQuality,
        qualification_reason: str,
    ) -> ConversationMetric:
        metric = self.get_or_create_by_conversation_id(conversation_id)
        now = utc_now()
        metric.used_human_transfer = True
        metric.final_outcome = FinalOutcome.HANDOFF
        metric.lead_quality = lead_quality
        metric.qualification_reason = qualification_reason.strip()
        metric.closed_at = now
        metric.updated_at = now
        self.db.add(metric)
        self.db.flush()
        self.db.refresh(metric)
        return metric

    def mark_retained(self, conversation_id: UUID) -> ConversationMetric:
        metric = self.get_or_create_by_conversation_id(conversation_id)
        if metric.final_outcome == FinalOutcome.HANDOFF:
            return metric
        now = utc_now()
        metric.final_outcome = FinalOutcome.RETAINED
        metric.closed_at = now
        metric.updated_at = now
        self.db.add(metric)
        self.db.flush()
        self.db.refresh(metric)
        return metric

    def mark_dropped(self, conversation_id: UUID) -> ConversationMetric:
        metric = self.get_or_create_by_conversation_id(conversation_id)
        if metric.final_outcome is not None:
            return metric
        now = utc_now()
        metric.final_outcome = FinalOutcome.DROPPED
        metric.closed_at = now
        metric.updated_at = now
        self.db.add(metric)
        self.db.flush()
        self.db.refresh(metric)
        return metric

    def mark_inactive_conversations_as_dropped(self, *, inactivity_hours: int = 12) -> int:
        cutoff = utc_now() - timedelta(hours=inactivity_hours)
        statement = (
            select(ConversationMetric)
            .join(Conversation, Conversation.id == ConversationMetric.conversation_id)
            .where(ConversationMetric.final_outcome.is_(None))
            .where(ConversationMetric.closed_at.is_(None))
            .where(Conversation.last_message_at.is_not(None))
            .where(Conversation.last_message_at <= cutoff)
        )
        metrics = list(self.db.exec(statement).all())
        for metric in metrics:
            self.mark_dropped(metric.conversation_id)
        return len(metrics)
