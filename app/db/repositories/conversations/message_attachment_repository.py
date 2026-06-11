from uuid import UUID

from sqlmodel import Session

from app.db.models.conversations import (
    MessageAttachment,
    MessageAttachmentCreate,
    MessageAttachmentUpdate,
)
from app.db.repositories.base import BaseRepository


class MessageAttachmentRepository(
    BaseRepository[MessageAttachment, MessageAttachmentCreate, MessageAttachmentUpdate, UUID]
):
    def __init__(self, db: Session):
        super().__init__(db, MessageAttachment)
