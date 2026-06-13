import logging
from typing import Any

from fastapi import APIRouter, Depends

from app.api.v1.admin_buildings import router as admin_buildings_router
from app.api.v1.webhooks.chatwoot import router as chatwoot_router
from app.core.auth import get_current_user
from app.core.auth.fake_users import FakeUser
from app.services.example import example_function

router = APIRouter()

logger = logging.getLogger(__name__)

router.include_router(chatwoot_router, tags=["chatwoot"])
router.include_router(admin_buildings_router)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "Health Check: v1"}


@router.get("/protected/example")
def example(user: FakeUser = Depends(get_current_user)) -> dict[str, Any]:
    logger.info("Example endpoint accessed by user: %s", user.user_id)
    text = example_function()
    return {"message": text, "user": user}
