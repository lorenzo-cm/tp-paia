import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter

from app.api.deps import SessionDep
from app.db.crud.user import create_user, get_user
from app.db.models.user import UserCreate

router = APIRouter()

logger = logging.getLogger(__name__)


@router.get("/user")
def read_user(db: SessionDep, user_id: UUID) -> Any:
    user = get_user(db, user_id)
    return {"user": user}


@router.post("/user")
def create_new_user(db: SessionDep, user_data: UserCreate) -> Any:
    user = create_user(db, user_data)
    return {"user": user}
