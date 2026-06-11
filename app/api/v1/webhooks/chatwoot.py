import asyncio
import logging

from fastapi import APIRouter, Depends

from app.services.chatwoot.factory import get_chatwoot_webhook_processor
from app.services.chatwoot.schemas.webhook import ChatwootWebhook
from app.services.chatwoot.webhook_processor import ChatwootWebhookProcessor

logger = logging.getLogger(__name__)

router = APIRouter()

_BG_TASKS: set[asyncio.Task[None]] = set()


def _on_task_done(task: "asyncio.Task[None]") -> None:
    _BG_TASKS.discard(task)
    if not task.cancelled() and task.exception() is not None:
        logger.error(
            "chatwoot webhook task crashed", exc_info=task.exception()
        )


@router.post("/webhook/chatwoot")
async def chatwoot_webhook(
    webhook: ChatwootWebhook,
    processor: ChatwootWebhookProcessor = Depends(get_chatwoot_webhook_processor),
) -> dict[str, str]:
    task = asyncio.create_task(processor.process(webhook))
    _BG_TASKS.add(task)
    task.add_done_callback(_on_task_done)
    return {"status": "ok"}
