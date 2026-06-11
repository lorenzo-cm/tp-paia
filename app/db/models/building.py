import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class BuildingBase(SQLModel):
    name: str = Field(index=True)
    information: str = Field(
        default="",
        sa_column=sa.Column(sa.Text(), nullable=False),
    )
    photos_url: list[str] = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB, nullable=False),
    )
    videos_url: list[str] = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB, nullable=False),
    )
    documents_url: list[str] = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB, nullable=False),
    )
    source_url: str | None = Field(default=None, index=True)
    extraction_version: str | None = None


class Building(BuildingBase, table=True):
    __tablename__ = "buildings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True, index=True)
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(sa.DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=sa.Column(
            sa.DateTime(timezone=True),
            nullable=False,
            onupdate=utc_now,
        ),
    )


class BuildingCreate(BuildingBase):
    pass


class BuildingUpdate(SQLModel):
    id: uuid.UUID
    name: str | None = None
    information: str | None = None
    photos_url: list[str] | None = None
    videos_url: list[str] | None = None
    documents_url: list[str] | None = None
    source_url: str | None = None
    extraction_version: str | None = None
