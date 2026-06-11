from uuid import UUID

from sqlalchemy import and_, asc, desc, exists, or_
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.core.pagination import PaginationParams, SortOrder
from app.db.models.conversations import Message, MessageCreate, MessageUpdate
from app.db.repositories.base import BaseRepository


class MessageRepository(BaseRepository[Message, MessageCreate, MessageUpdate, UUID]):
    def __init__(self, db: Session):
        super().__init__(db, Message)

    def exists_by_external_id(self, external_message_id: int) -> bool:
        """Cheap idempotency check for webhook replays."""
        statement = select(
            exists().where(Message.external_message_id == external_message_id)  # type: ignore[arg-type]
        )
        return bool(self.db.exec(statement).one())

    def list_recent_with_attachments(
        self, conversation_id: UUID, limit: int
    ) -> list[Message]:
        """Last ``limit`` messages of a conversation in chronological order,
        with attachments eager-loaded (single round-trip)."""
        statement = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(desc(Message.sent_at), desc(Message.id))  # type: ignore[arg-type]
            .limit(limit)
            .options(selectinload(Message.attachments))  # type: ignore[arg-type]
        )
        recent = list(self.db.exec(statement).all())
        recent.reverse()
        return recent

    def list_by_conversation_cursor(
        self, conversation_id: UUID, pagination: PaginationParams
    ) -> list[Message]:
        statement = select(Message).where(Message.conversation_id == conversation_id)

        if pagination.after is not None:
            if pagination.sort_order == SortOrder.DESC:
                if pagination.after_id is not None:
                    statement = statement.where(
                        or_(
                            Message.sent_at < pagination.after,
                            and_(
                                Message.sent_at == pagination.after,
                                Message.id < pagination.after_id,
                            ),
                        )
                    )
                else:
                    statement = statement.where(Message.sent_at < pagination.after)
            else:
                if pagination.after_id is not None:
                    statement = statement.where(
                        or_(
                            Message.sent_at > pagination.after,
                            and_(
                                Message.sent_at == pagination.after,
                                Message.id > pagination.after_id,
                            ),
                        )
                    )
                else:
                    statement = statement.where(Message.sent_at > pagination.after)

        if pagination.sort_order == SortOrder.DESC:
            statement = statement.order_by(desc(Message.sent_at), desc(Message.id))
        else:
            statement = statement.order_by(asc(Message.sent_at), asc(Message.id))

        statement = statement.limit(pagination.limit)
        return list(self.db.exec(statement).all())
