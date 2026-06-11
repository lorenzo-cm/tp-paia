"""MessageRepository: idempotency check and recent listing with attachments."""

from sqlmodel import Session

from app.db.models.conversations import InteractionType
from app.db.repositories.conversations import MessageRepository

from .factories import (
    make_attachment,
    make_full_thread,
    make_message,
    next_external_id,
)


class TestExistsByExternalId:
    def test_returns_true_when_message_present(self, db_session: Session) -> None:
        conversation, participant, _ = make_full_thread(db_session)
        external_id = next_external_id()
        make_message(db_session, conversation.id, participant.id, external_id=external_id)

        assert MessageRepository(db_session).exists_by_external_id(external_id) is True


class TestListRecentWithAttachments:
    def test_returns_chronological_order_within_limit(
        self, db_session: Session
    ) -> None:
        conversation, _, _ = make_full_thread(db_session, message_count=5)

        result = MessageRepository(db_session).list_recent_with_attachments(
            conversation.id, limit=3
        )

        assert len(result) == 3
        timestamps = [m.sent_at for m in result]
        assert timestamps == sorted(timestamps), "expected ascending sent_at"

    def test_attachments_remain_accessible_after_session_expire(
        self, db_session: Session
    ) -> None:
        conversation, participant, _ = make_full_thread(db_session, message_count=0)
        message = make_message(db_session, conversation.id, participant.id)
        make_attachment(db_session, message.id)
        make_attachment(db_session, message.id)
        db_session.expire_all()

        result = MessageRepository(db_session).list_recent_with_attachments(
            conversation.id, limit=10
        )

        # If attachments were lazy, accessing them after expire would either
        # raise DetachedInstanceError or trigger a hidden round-trip — both
        # break the contract this method exists to guarantee.
        assert len(result[0].attachments) == 2


class TestToolInteractionPersistence:
    def test_tool_call_and_tool_response_can_be_persisted(
        self, db_session: Session
    ) -> None:
        conversation, participant, _ = make_full_thread(db_session, message_count=0)
        tool_call = make_message(
            db_session,
            conversation.id,
            participant.id,
            content='{"name":"get_building_info","arguments":{"building_id":"10"}}',
            interaction_type=InteractionType.TOOL_CALL,
        )
        tool_response = make_message(
            db_session,
            conversation.id,
            participant.id,
            content='{"success":false,"tool_output":{"type":"get_building_info"}}',
            interaction_type=InteractionType.TOOL_RESPONSE,
        )

        recent = MessageRepository(db_session).list_recent_with_attachments(
            conversation.id, limit=10
        )

        assert [m.interaction_type for m in recent] == [
            InteractionType.TOOL_CALL,
            InteractionType.TOOL_RESPONSE,
        ]
        assert tool_call.content is not None
        assert tool_response.content is not None
