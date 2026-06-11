"""Tiny builders to keep test bodies focused on assertions, not setup noise."""

from itertools import count
from uuid import UUID

from sqlmodel import Session

from app.db.models.conversations import (
    Contact,
    ContactCreate,
    Conversation,
    ConversationCreate,
    ConversationParticipant,
    ConversationParticipantCreate,
    ConversationStatus,
    InteractionType,
    Message,
    MessageAttachment,
    MessageAttachmentCreate,
    MessageCreate,
    ParticipantType,
    SenderType,
)
from app.db.repositories.conversations import (
    ContactRepository,
    ConversationParticipantRepository,
    ConversationRepository,
    MessageAttachmentRepository,
    MessageRepository,
)

# Deterministic external-id source — never collides, never depends on uuid randomness.
_external_id_counter = count(1)


def next_external_id() -> int:
    return next(_external_id_counter)


def build_conversation_create(
    *, external_id: int | None = None, inbox_id: int = 1
) -> ConversationCreate:
    return ConversationCreate(
        inbox_id=inbox_id,
        external_conversation_id=external_id,
        status=ConversationStatus.OPEN,
    )


def build_contact_create(
    *, external_id: int | None = None, name: str = "Test Contact"
) -> ContactCreate:
    return ContactCreate(external_contact_id=external_id, name=name)


def make_contact(db: Session, *, external_id: int | None = None) -> Contact:
    return ContactRepository(db).create(build_contact_create(external_id=external_id))


def make_conversation(
    db: Session, *, external_id: int | None = None, inbox_id: int = 1
) -> Conversation:
    return ConversationRepository(db).create(
        build_conversation_create(external_id=external_id, inbox_id=inbox_id)
    )


def make_participant(
    db: Session,
    conversation_id: UUID,
    *,
    contact_id: UUID | None = None,
    participant_type: ParticipantType = ParticipantType.CONTACT,
) -> ConversationParticipant:
    return ConversationParticipantRepository(db).create(
        ConversationParticipantCreate(
            conversation_id=conversation_id,
            participant_type=participant_type,
            contact_id=contact_id,
        )
    )


def make_message(
    db: Session,
    conversation_id: UUID,
    sender_participant_id: UUID | None,
    *,
    external_id: int | None = None,
    content: str = "hello",
    sender_type: SenderType = SenderType.USER,
    interaction_type: InteractionType = InteractionType.CHAT,
) -> Message:
    return MessageRepository(db).create(
        MessageCreate(
            conversation_id=conversation_id,
            sender_participant_id=sender_participant_id,
            sender_type=sender_type,
            interaction_type=interaction_type,
            external_message_id=external_id,
            content=content,
        )
    )


def make_attachment(
    db: Session, message_id: UUID, *, url: str = "https://example/x.png"
) -> MessageAttachment:
    return MessageAttachmentRepository(db).create(
        MessageAttachmentCreate(message_id=message_id, url=url, mime_type="image/png")
    )


def make_full_thread(
    db: Session, *, message_count: int = 1
) -> tuple[Conversation, ConversationParticipant, list[Message]]:
    """Conversation + one CONTACT participant + N messages, all wired up."""
    contact = make_contact(db, external_id=next_external_id())
    conversation = make_conversation(db, external_id=next_external_id())
    participant = make_participant(db, conversation.id, contact_id=contact.id)
    messages = [
        make_message(db, conversation.id, participant.id, content=f"msg {i}")
        for i in range(message_count)
    ]
    return conversation, participant, messages
