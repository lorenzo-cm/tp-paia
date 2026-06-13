from __future__ import annotations

from sqlmodel import SQLModel

from app.db.models import BuildingCreate


class BuildingCreateRequest(BuildingCreate):
    pass


class BuildingUpdateRequest(SQLModel):
    name: str | None = None
    information: str | None = None
    photos_url: list[str] | None = None
    videos_url: list[str] | None = None
    documents_url: list[str] | None = None
    source_url: str | None = None
    extraction_version: str | None = None
