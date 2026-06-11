from app.db.models.conversations import (
    ContactCreate,
    Conversation,
    ConversationCreate,
    ConversationParticipant,
    Message,
    MessageCreate,
    ParticipantType,
    SenderType,
)
from app.db.models.conversations.message import utc_now
from app.services.message_processing.deps import Repos
from app.services.message_processing.schemas import (
    ConversationContext,
    InboundAttachment,
    InboundMessage,
)

DEFAULT_CONVERSATION_META = {
    "sales_stage": "initial_contact",
    "last_building_id": None,
    "handoff_requested": False,
}


def save_user_messages(batch: list[InboundMessage], repos: Repos) -> ConversationContext:
    """Dedup the burst, resolve conversation, write USER rows.

    Flushes via repos but does not commit — the pipeline owns the transaction.
    """
    deduped = deduplicate_messages(batch)
    first = deduped[0]
    conv, contact_part, bot_part = resolve_conversation(first, repos)
    items = _write_user_messages(deduped, conv, contact_part, repos)
    return ConversationContext(
        conversation_id=conv.id,
        conv_ext_id=int(first.external_conversation_id),
        bot_participant_id=bot_part.id,
        items=items,
    )


def deduplicate_messages(batch: list[InboundMessage]) -> list[InboundMessage]:
    """Drop repeated ``external_message_id`` values, keeping first-seen order."""
    deduped: list[InboundMessage] = []
    seen: set[str] = set()
    for m in batch:
        if m.external_message_id in seen:
            continue
        seen.add(m.external_message_id)
        deduped.append(m)
    return deduped


def resolve_conversation(
    first: InboundMessage, repos: Repos
) -> tuple[Conversation, ConversationParticipant, ConversationParticipant]:
    """Get or create conversation, contact, and CONTACT/BOT participants."""
    conv = repos.conversation.get_or_create_by_external_id(
        int(first.external_conversation_id),
        ConversationCreate(
            inbox_id=int(first.inbox_ref),
            external_conversation_id=int(first.external_conversation_id),
            meta=DEFAULT_CONVERSATION_META.copy(),
        ),
    )
    if not conv.meta:
        conv.meta = DEFAULT_CONVERSATION_META.copy()
        repos.conversation.db.add(conv)
        repos.conversation.db.flush()
    contact = repos.contact.get_or_create_by_external_id(
        int(first.contact_external_id),
        ContactCreate(
            external_contact_id=int(first.contact_external_id),
            name=first.contact_name,
            phone=first.contact_phone,
        ),
    )
    contact_part = repos.participant.get_or_create(
        conv.id, ParticipantType.CONTACT, contact_id=contact.id
    )
    bot_part = repos.participant.get_or_create(conv.id, ParticipantType.BOT)
    repos.metric.get_or_create_by_conversation_id(conv.id)
    return conv, contact_part, bot_part


def _write_user_messages(
    deduped: list[InboundMessage],
    conv: Conversation,
    contact_part: ConversationParticipant,
    repos: Repos,
) -> list[tuple[InboundMessage, Message, list[InboundAttachment]]]:
    """Insert USER messages for new external ids; skip DB duplicates."""
    items: list[tuple[InboundMessage, Message, list[InboundAttachment]]] = []
    for m in deduped:
        if repos.message.exists_by_external_id(int(m.external_message_id)):
            continue
        row = repos.message.create(
            MessageCreate(
                conversation_id=conv.id,
                sender_participant_id=contact_part.id,
                sender_type=SenderType.USER,
                external_message_id=int(m.external_message_id),
                content=m.text,
                sent_at=m.sent_at or utc_now(),
            )
        )
        items.append((m, row, list(m.attachments)))
    return items
