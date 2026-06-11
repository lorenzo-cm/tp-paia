from uuid import UUID

from sqlmodel import Session, select

from app.db.models.conversations import (
    ConversationParticipant,
    ConversationParticipantCreate,
    ConversationParticipantUpdate,
    ParticipantType,
)
from app.db.repositories.base import BaseRepository


class ConversationParticipantRepository(
    BaseRepository[
        ConversationParticipant,
        ConversationParticipantCreate,
        ConversationParticipantUpdate,
        UUID,
    ]
):
    def __init__(self, db: Session):
        super().__init__(db, ConversationParticipant)

    def get_by_conversation_and_contact(
        self, conversation_id: UUID, contact_id: UUID
    ) -> ConversationParticipant | None:
        statement = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.contact_id == contact_id,
        )
        return self.db.exec(statement).first()

    def get_or_create(
        self,
        conversation_id: UUID,
        participant_type: ParticipantType,
        contact_id: UUID | None = None,
        agent_user_id: UUID | None = None,
    ) -> ConversationParticipant:
        """Idempotent participant lookup. Matches on (conversation_id, contact_id)
        for CONTACT participants, on (conversation_id, agent_user_id) for AGENT
        participants, and on (conversation_id, participant_type=BOT) for the
        single BOT participant per conversation.

        Caller owns the surrounding transaction; this method only flushes.
        """
        statement = select(ConversationParticipant).where(
            ConversationParticipant.conversation_id == conversation_id,
            ConversationParticipant.participant_type == participant_type,
        )
        if contact_id is not None:
            statement = statement.where(
                ConversationParticipant.contact_id == contact_id
            )
        if agent_user_id is not None:
            statement = statement.where(
                ConversationParticipant.agent_user_id == agent_user_id
            )

        existing = self.db.exec(statement).first()
        if existing is not None:
            return existing

        return self.create(
            ConversationParticipantCreate(
                conversation_id=conversation_id,
                participant_type=participant_type,
                contact_id=contact_id,
                agent_user_id=agent_user_id,
            )
        )
