from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.db.models import Building, BuildingCreate, BuildingUpdate
from app.db.repositories import BuildingRepository
from app.services.real_estate_rag.service import BuildingRAGService
from app.services.real_estate_rag.tasks import schedule_building_reindex


@dataclass(slots=True)
class ReindexSummary:
    requested: int
    building_ids: list[str]


class CatalogAdminService:
    def __init__(
        self,
        *,
        repository: BuildingRepository,
        rag_service: BuildingRAGService,
    ) -> None:
        self._repository = repository
        self._rag_service = rag_service

    @classmethod
    def from_session(cls, db: Session, rag_service: BuildingRAGService) -> CatalogAdminService:
        return cls(repository=BuildingRepository(db), rag_service=rag_service)

    def list_buildings(self) -> list[dict[str, Any]]:
        return [
            self._serialize_summary(building)
            for building in self._repository.list_all()
        ]

    def get_building(self, building_id: UUID | str) -> Building | None:
        return self._repository.get_building_by_tool_id(building_id)

    def create_building(self, payload: BuildingCreate) -> tuple[Building, bool]:
        building = self._repository.create(payload, flush=True)
        return building, True

    def update_building(self, building_id: UUID, payload: BuildingUpdate) -> tuple[Building, bool]:
        building = self._repository.update(payload.model_copy(update={"id": building_id}), flush=True)
        return building, True

    def reindex_building(self, building_id: UUID | str) -> bool:
        building = self._repository.get_building_by_tool_id(building_id)
        if building is None:
            return False
        schedule_building_reindex(self._repository.serialize_rag_payload(building))
        return True

    def reindex_all(self) -> ReindexSummary:
        building_ids: list[str] = []
        for building in self._repository.list_all():
            schedule_building_reindex(self._repository.serialize_rag_payload(building))
            building_ids.append(str(building.id))
        return ReindexSummary(requested=len(building_ids), building_ids=building_ids)

    def rag_status(self) -> dict[str, Any]:
        buildings = self._repository.list_all()
        return {
            "collection_name": self._rag_service.collection_name,
            "catalog_building_count": len(buildings),
            "building_ids": [str(building.id) for building in buildings],
        }

    def rag_search(
        self, *, query: str, building_id: UUID | str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        hits = self._rag_service.search(query, session=self._repository.db, building_id=building_id, limit=limit)
        return {
            "query": query,
            "building_id": str(building_id) if building_id is not None else None,
            "matches": [asdict(hit) for hit in hits],
            "context": self._rag_service.render_context(hits),
        }

    def _serialize_summary(self, building: Building) -> dict[str, Any]:
        return {
            "building_id": str(building.id),
            "name": building.name,
            "source_url": building.source_url,
            "photos_total": len(building.photos_url or []),
            "videos_total": len(building.videos_url or []),
            "documents_total": len(building.documents_url or []),
            "extraction_version": building.extraction_version,
            "updated_at": building.updated_at,
        }
