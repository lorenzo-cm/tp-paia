"""Parâmetros de listagem (cursor) — Pydantic compartilhado por API/repos (antes ``schemas/``)."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class SortOrder(StrEnum):
    ASC = "asc"
    DESC = "desc"


class PaginationParams(BaseModel):
    after: datetime | None = Field(
        default=None,
        description="Cursor: sent_at of the last item from the previous page",
    )
    after_id: UUID | None = Field(
        default=None,
        description="Tie-breaker cursor for stable pagination when timestamps match",
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    sort_order: SortOrder = Field(
        default=SortOrder.DESC,
        description="Sort order by sent_at",
    )
