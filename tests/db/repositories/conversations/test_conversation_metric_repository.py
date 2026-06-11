from datetime import timedelta

from sqlmodel import Session

from app.db.models.conversations import FinalOutcome, LeadQuality
from app.db.repositories.conversations import ConversationMetricRepository

from .factories import make_conversation


class TestConversationMetricRepository:
    def test_get_or_create_by_conversation_id_creates_single_row(
        self, db_session: Session
    ) -> None:
        conversation = make_conversation(db_session, external_id=1001)
        repo = ConversationMetricRepository(db_session)

        metric = repo.get_or_create_by_conversation_id(conversation.id)
        same_metric = repo.get_or_create_by_conversation_id(conversation.id)

        assert metric.id == same_metric.id
        assert metric.conversation_id == conversation.id
        assert metric.tool_usage == {}

    def test_updates_quality_tool_usage_and_response_times(
        self, db_session: Session
    ) -> None:
        conversation = make_conversation(db_session, external_id=1002)
        repo = ConversationMetricRepository(db_session)

        repo.update_lead_quality(
            conversation.id,
            LeadQuality.MEDIUM,
            "Lead demonstrou interesse no empreendimento.",
        )
        repo.increment_tool_usage(conversation.id, "search_building_information")
        repo.increment_tool_usage(conversation.id, "search_building_information")
        repo.increment_tool_usage(conversation.id, "transfer_human")
        repo.record_response_time(conversation.id, 4800)
        metric = repo.record_response_time(conversation.id, 1200)

        assert metric.lead_quality == LeadQuality.MEDIUM
        assert metric.qualification_reason == "Lead demonstrou interesse no empreendimento."
        assert metric.tool_usage == {
            "search_building_information": 2,
            "transfer_human": 1,
        }
        assert metric.response_time_min_ms == 1200
        assert metric.response_time_max_ms == 4800
        assert metric.response_time_count == 2

    def test_mark_handoff_retained_and_dropped(
        self, db_session: Session
    ) -> None:
        handoff_conversation = make_conversation(db_session, external_id=1003)
        retained_conversation = make_conversation(db_session, external_id=1004)
        dropped_conversation = make_conversation(db_session, external_id=1005)
        repo = ConversationMetricRepository(db_session)

        handoff_metric = repo.mark_handoff(
            handoff_conversation.id,
            lead_quality=LeadQuality.HIGH,
            qualification_reason="Pediu visita e falou em proposta.",
        )
        retained_metric = repo.mark_retained(retained_conversation.id)
        dropped_metric = repo.mark_dropped(dropped_conversation.id)

        assert handoff_metric.used_human_transfer is True
        assert handoff_metric.final_outcome == FinalOutcome.HANDOFF
        assert handoff_metric.closed_at is not None
        assert retained_metric.final_outcome == FinalOutcome.RETAINED
        assert retained_metric.closed_at is not None
        assert dropped_metric.final_outcome == FinalOutcome.DROPPED
        assert dropped_metric.closed_at is not None

    def test_mark_inactive_conversations_as_dropped(
        self, db_session: Session
    ) -> None:
        stale_conversation = make_conversation(db_session, external_id=1006)
        fresh_conversation = make_conversation(db_session, external_id=1007)
        repo = ConversationMetricRepository(db_session)
        stale_metric = repo.get_or_create_by_conversation_id(stale_conversation.id)
        fresh_metric = repo.get_or_create_by_conversation_id(fresh_conversation.id)
        stale_conversation.last_message_at = stale_metric.updated_at - timedelta(hours=13)
        fresh_conversation.last_message_at = fresh_metric.updated_at - timedelta(hours=1)
        db_session.add(stale_conversation)
        db_session.add(fresh_conversation)
        db_session.flush()

        dropped = repo.mark_inactive_conversations_as_dropped()

        assert dropped == 1
        assert repo.get(stale_metric.id, raise_exception=True).final_outcome == FinalOutcome.DROPPED
        assert repo.get(fresh_metric.id, raise_exception=True).final_outcome is None
