"""Relationship & schema invariants: cascade, SET NULL, JSON roundtrip, tz."""

from sqlmodel import Session, select

from app.db.models.conversations import (
    Conversation,
    ConversationParticipant,
    Message,
    MessageAttachment,
    MessageCreate,
    SenderType,
)
from app.db.repositories.conversations import (
    ConversationParticipantRepository,
    ConversationRepository,
    MessageRepository,
)

from .factories import (
    make_attachment,
    make_full_thread,
    make_message,
)


class TestCascade:
    def test_conversation_delete_cascades_to_messages_and_participants(
        self, db_session: Session
    ) -> None:
        conversation, _, _ = make_full_thread(db_session, message_count=2)
        ConversationRepository(db_session).delete(conversation)
        db_session.flush()

        remaining_messages = db_session.exec(
            select(Message).where(Message.conversation_id == conversation.id)
        ).all()
        remaining_participants = db_session.exec(
            select(ConversationParticipant).where(
                ConversationParticipant.conversation_id == conversation.id
            )
        ).all()

        assert remaining_messages == []
        assert remaining_participants == []

    def test_message_delete_cascades_to_attachments(
        self, db_session: Session
    ) -> None:
        conversation, participant, _ = make_full_thread(db_session, message_count=0)
        message = make_message(db_session, conversation.id, participant.id)
        make_attachment(db_session, message.id)
        make_attachment(db_session, message.id)

        MessageRepository(db_session).delete(message)
        db_session.flush()

        remaining = db_session.exec(
            select(MessageAttachment).where(
                MessageAttachment.message_id == message.id
            )
        ).all()
        assert remaining == []


class TestSetNull:
    def test_deleting_participant_nulls_message_sender(
        self, db_session: Session
    ) -> None:
        conversation, participant, messages = make_full_thread(
            db_session, message_count=1
        )
        message_id = messages[0].id

        ConversationParticipantRepository(db_session).delete(participant)
        db_session.flush()
        db_session.expire_all()

        reloaded = db_session.get(Message, message_id)
        assert reloaded is not None, "message must survive participant deletion"
        assert reloaded.sender_participant_id is None


class TestMetaRoundtrip:
    def test_meta_json_persists_and_reads_back(self, db_session: Session) -> None:
        conversation, participant, _ = make_full_thread(db_session, message_count=0)
        payload = {"chatwoot_status": "delivered", "delivery_attempts": 2}

        message = MessageRepository(db_session).create(
            MessageCreate(
                conversation_id=conversation.id,
                sender_participant_id=participant.id,
                sender_type=SenderType.USER,
                content="hi",
                meta=payload,
            )
        )
        db_session.expire_all()

        reloaded = db_session.get(Message, message.id)
        assert reloaded is not None
        assert reloaded.meta == payload


class TestTimezoneAware:
    def test_conversation_timestamps_are_tz_aware(self, db_session: Session) -> None:
        conversation, _, _ = make_full_thread(db_session, message_count=0)
        db_session.expire_all()

        reloaded = db_session.get(Conversation, conversation.id)
        assert reloaded is not None
        assert reloaded.created_at.tzinfo is not None
        assert reloaded.updated_at.tzinfo is not None
