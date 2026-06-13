from dataclasses import dataclass, field
from uuid import UUID

from app.db.models.conversations import Message
from app.services.agent.base import AgentAttachment
from app.services.message_processing.schemas.inbound import (
    InboundAttachment,
    InboundMessage,
)
from app.services.real_estate_rag.schemas import RagHit


@dataclass
class ConversationContext:
    """After save step: conversation ids and saved USER rows for this burst."""

    conversation_id: UUID
    conv_ext_id: int
    bot_participant_id: UUID
    items: list[tuple[InboundMessage, Message, list[InboundAttachment]]] = field(
        default_factory=list
    )


@dataclass
class Enriched:
    """After enrich step: combined text and attachments for the agent."""

    combined_text: str
    agent_attachments: list[AgentAttachment] = field(default_factory=list)
    rag_context: list[RagHit] = field(default_factory=list)
