"""Tiny builders for building catalog repository tests."""

from itertools import count
from typing import Any

from sqlmodel import Session

from app.db.models import Building, BuildingCreate
from app.db.repositories import BuildingRepository

_building_counter = count(1)


def next_source_url() -> str:
    return f"https://example.com/buildings/{next(_building_counter)}"


def build_building_create(
    *,
    name: str = "Residencial Aurora",
    source_url: str | None = None,
    information: str | None = None,
    photos_url: list[str] | None = None,
    videos_url: list[str] | None = None,
    documents_url: list[str] | None = None,
    extraction_version: str | None = "v1",
) -> BuildingCreate:
    return BuildingCreate(
        name=name,
        information=information
        or "Empreendimento premium com áreas de lazer, boa localização e unidades modernas.",
        photos_url=photos_url
        or [
            "https://cdn.example.com/buildings/aurora/fachada.jpg",
            "https://cdn.example.com/buildings/aurora/piscina.jpg",
        ],
        videos_url=videos_url or ["https://cdn.example.com/buildings/aurora/tour.mp4"],
        documents_url=documents_url or ["https://cdn.example.com/buildings/aurora.pdf"],
        source_url=source_url or next_source_url(),
        extraction_version=extraction_version,
    )


def make_building(db: Session, **overrides: Any) -> Building:
    payload = build_building_create(**overrides)
    return BuildingRepository(db).create(payload)
