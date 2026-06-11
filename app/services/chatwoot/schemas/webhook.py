from typing import Any, Literal

from pydantic import BaseModel


class Account(BaseModel):
    id: int
    name: str


class ContactInbox(BaseModel):
    id: int
    contact_id: int
    inbox_id: int
    source_id: str | None = None
    created_at: str
    updated_at: str
    hmac_verified: bool
    pubsub_token: str


class Sender(BaseModel):
    additional_attributes: dict[str, Any]
    custom_attributes: dict[str, Any]
    email: str | None
    id: int
    identifier: str | None
    name: str
    phone_number: str | None = None
    thumbnail: str
    type: str | None = None
    avatar: str | None = None
    account: Account | None = None


class MessageConversation(BaseModel):
    """Nested conversation info within a message"""

    assignee_id: int | None
    unread_count: int
    last_activity_at: int
    contact_inbox: dict[str, str]


class Message(BaseModel):
    id: int
    content: str | None
    account_id: int
    inbox_id: int
    conversation_id: int
    message_type: int
    created_at: int
    updated_at: str
    private: bool
    status: str
    source_id: str | None = None
    content_type: str
    content_attributes: dict[str, Any]
    sender_type: str
    sender_id: int
    external_source_ids: dict[str, Any] | None = None
    additional_attributes: dict[str, Any]
    processed_message_content: str | None
    sentiment: dict[str, Any]
    conversation: MessageConversation
    sender: Sender


class Meta(BaseModel):
    sender: Sender
    assignee: Any | None
    team: Any | None
    hmac_verified: bool


class Conversation(BaseModel):
    additional_attributes: dict[str, Any]
    can_reply: bool
    channel: str
    contact_inbox: ContactInbox
    id: int
    inbox_id: int
    messages: list[Message]
    labels: list[Any]
    meta: Meta
    status: str
    custom_attributes: dict[str, Any]
    snoozed_until: str | None
    unread_count: int
    first_reply_created_at: str | None
    priority: str | None
    waiting_since: int
    agent_last_seen_at: int
    contact_last_seen_at: int
    last_activity_at: int
    timestamp: int
    created_at: int


class Inbox(BaseModel):
    id: int
    name: str


class Attachment(BaseModel):
    """Attachment info in Chatwoot message"""

    id: int
    message_id: int
    file_type: str  # 'image', 'audio', 'video', 'file'
    account_id: int
    extension: str | None = None
    data_url: str
    thumb_url: str | None = None
    file_size: int | None = None


class ChatwootWebhook(BaseModel):
    """
    Chatwoot webhook payload for message_created event.

    This model validates the incoming webhook data from Chatwoot.
    """

    account: Account
    additional_attributes: dict[str, Any]
    content_attributes: dict[str, Any]
    content_type: str
    content: str | None  # Can be None for messages with only attachments
    conversation: Conversation
    created_at: str
    id: int
    inbox: Inbox
    message_type: Literal["incoming", "outgoing"]
    private: bool
    sender: Sender
    source_id: str | None = None
    event: str
    attachments: list[Attachment] = []

    def get_message_content(self) -> str:
        """Helper method to get the message content"""
        return self.content or ""

    def get_inbox_id(self) -> int:
        """Helper method to get the inbox ID"""
        return self.inbox.id

    def get_conversation_id(self) -> int:
        """Helper method to get the conversation ID"""
        return self.conversation.id

    def get_account_id(self) -> int:
        """Helper method to get the account ID"""
        return self.account.id

    def get_sender_name(self) -> str:
        """Helper method to get the sender name"""
        return self.sender.name

    def get_sender_phone(self) -> str | None:
        """Helper method to get the sender phone number"""
        return self.sender.phone_number

    def is_incoming_message(self) -> bool:
        """Check if this is an incoming message"""
        return self.message_type == "incoming"

    def has_attachments(self) -> bool:
        """Check if message has attachments"""
        return len(self.attachments) > 0

    def get_audio_attachments(self) -> list[Attachment]:
        """Get all audio attachments"""
        return [att for att in self.attachments if att.file_type == "audio"]

    def get_image_attachments(self) -> list[Attachment]:
        """Get all image attachments"""
        return [att for att in self.attachments if att.file_type == "image"]

    def get_file_attachments(self) -> list[Attachment]:
        """Get all file attachments (excluding audio, image, video)"""
        return [att for att in self.attachments if att.file_type == "file"]
