"""ConversationParticipantRepository: idempotent get_or_create."""

from sqlmodel import Session

from app.db.models.conversations import ParticipantType
from app.db.repositories.conversations import ConversationParticipantRepository

from .factories import make_contact, make_conversation, make_participant


class TestGetOrCreate:
    def test_persists_new_participant_with_requested_type(
        self, db_session: Session
    ) -> None:
        conversation = make_conversation(db_session)
        contact = make_contact(db_session)

        participant = ConversationParticipantRepository(db_session).get_or_create(
            conversation_id=conversation.id,
            participant_type=ParticipantType.CONTACT,
            contact_id=contact.id,
        )

        assert participant.participant_type == ParticipantType.CONTACT
        assert participant.contact_id == contact.id

    def test_returns_existing_participant_when_already_present(
        self, db_session: Session
    ) -> None:
        conversation = make_conversation(db_session)
        contact = make_contact(db_session)
        first = make_participant(db_session, conversation.id, contact_id=contact.id)

        second = ConversationParticipantRepository(db_session).get_or_create(
            conversation_id=conversation.id,
            participant_type=ParticipantType.CONTACT,
            contact_id=contact.id,
        )

        assert second.id == first.id
