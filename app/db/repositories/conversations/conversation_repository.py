from uuid import UUID

from sqlmodel import Session, select

from app.db.models.conversations import (
    Conversation,
    ConversationCreate,
    ConversationUpdate,
)
from app.db.repositories.base import BaseRepository


class ConversationRepository(
    BaseRepository[Conversation, ConversationCreate, ConversationUpdate, UUID]
):
    def __init__(self, db: Session):
        super().__init__(db, Conversation)

    def get_with_lock(self, conversation_id: UUID) -> Conversation | None:
        """Fetch a conversation with a row-level lock (SELECT ... FOR UPDATE).

        Used by callers that need to mutate the row inside a transaction
        without races against concurrent webhooks for the same conversation.
        """
        statement = (
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .with_for_update()
        )
        return self.db.exec(statement).first()

    def get_by_external_id(self, external_id: int) -> Conversation | None:
        statement = select(Conversation).where(
            Conversation.external_conversation_id == external_id
        )
        return self.db.exec(statement).first()

    def get_or_create_by_external_id(
        self, external_id: int, defaults: ConversationCreate
    ) -> Conversation:
        """Idempotent upsert keyed by external_conversation_id.

        Caller owns the surrounding transaction; this method only flushes,
        never commits.
        """
        existing = self.get_by_external_id(external_id)
        if existing is not None:
            return existing
        return self.create(defaults)
