from sqlmodel import Session

from app.db.repositories import (
    BuildingRepository,
    ContactRepository,
    ConversationMetricRepository,
    ConversationParticipantRepository,
    ConversationRepository,
    MessageAttachmentRepository,
    MessageRepository,
)


class Repos:
    """Conversation repositories bound to one pipeline ``Session``."""

    def __init__(self, db: Session) -> None:
        self.building = BuildingRepository(db)
        self.contact = ContactRepository(db)
        self.conversation = ConversationRepository(db)
        self.metric = ConversationMetricRepository(db)
        self.participant = ConversationParticipantRepository(db)
        self.message = MessageRepository(db)
        self.message_attachment = MessageAttachmentRepository(db)
