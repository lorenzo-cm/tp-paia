from app.services.message_debouncer.service import MessageDebouncer
from app.services.message_processing.schemas import (
    InboundMessage,
    deserialize_inbound,
    serialize_inbound,
)


async def debounce(
    debouncer: MessageDebouncer, msg: InboundMessage
) -> list[InboundMessage] | None:
    """Buffer this message and wait for the burst to settle.

    Returns ``None`` while the window is still open (pipeline exits early).
    Returns the full batch as ``InboundMessage`` list when this caller is final.
    """
    info = await debouncer.debounce(
        msg.external_conversation_id, serialize_inbound(msg)
    )
    if info is None:
        return None
    return [deserialize_inbound(p) for p in info.payloads]
