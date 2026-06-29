import logging
import re
import unicodedata
import uuid
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.db.models import Building, BuildingCreate, BuildingUpdate
from app.db.models.building import utc_now
from app.db.repositories.base import BaseRepository
from app.db.repositories.exceptions import RepositoryUpdateError
from app.services.real_estate_rag.tasks import schedule_building_reindex

logger = logging.getLogger(__name__)


def normalize_catalog_name(name: str) -> str:
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode(
        "ascii"
    )
    text = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
    return re.sub(r"\s+", " ", text)


def _coerce_building_id(building_id: uuid.UUID | str) -> uuid.UUID:
    if isinstance(building_id, uuid.UUID):
        return building_id
    return uuid.UUID(str(building_id))


class BuildingRepository(
    BaseRepository[Building, BuildingCreate, BuildingUpdate, uuid.UUID]
):
    def __init__(self, db: Session):
        super().__init__(db, Building)

    def list_all(self) -> list[Building]:
        statement = select(Building).order_by(Building.name.asc(), Building.id.asc())
        return list(self.db.exec(statement).all())

    def create(self, create_model: BuildingCreate, *, flush: bool = True) -> Building:
        building = super().create(create_model, flush=flush)
        self._queue_rag_reindex(building)
        return building

    def get_by_source_url(self, source_url: str) -> Building | None:
        statement = select(Building).where(Building.source_url == source_url)
        return self.db.exec(statement).first()

    def get_or_create_by_source_url(
        self, source_url: str, defaults: BuildingCreate
    ) -> Building:
        existing = self.get_by_source_url(source_url)
        if existing is not None:
            return existing
        return self.create(defaults)

    def update(
        self,
        update_data: BuildingUpdate | Building,
        *,
        exclude_none: bool = True,
        flush: bool = True,
    ) -> Building:
        try:
            entity = self.get(update_data.id, raise_exception=True)

            dump_kwargs: dict[str, Any] = {"exclude_unset": True, "exclude": {"id"}}
            if exclude_none:
                dump_kwargs["exclude_none"] = True
            values = update_data.model_dump(**dump_kwargs)

            for key, value in values.items():
                setattr(entity, key, value)

            entity.updated_at = utc_now()
            self.db.add(entity)
            if flush:
                self.db.flush()
                self.db.refresh(entity)
            self._queue_rag_reindex(entity)
            return entity
        except SQLAlchemyError as exc:
            raise RepositoryUpdateError(
                f"Failed to update {self.model.__name__}: {exc}"
            ) from exc

    def _rag_payload(self, building: Building) -> dict[str, Any]:
        return {
            "building_id": str(building.id),
            "building_name": building.name,
            "source_url": building.source_url,
            "information": building.information or "",
            "extraction_version": building.extraction_version,
            "photos_url": building.photos_url or [],
            "videos_url": building.videos_url or [],
            "documents_url": building.documents_url or [],
        }

    def serialize_rag_payload(self, building: Building) -> dict[str, Any]:
        return self._rag_payload(building)

    def _queue_rag_reindex(self, building: Building) -> None:
        try:
            schedule_building_reindex(self._rag_payload(building))
        except Exception:
            logger.warning(
                "Failed to queue building RAG reindex for %s", building.id, exc_info=True
            )

    def _building_list_item(self, building: Building) -> dict[str, Any]:
        return {
            "building_id": str(building.id),
            "building_name": building.name,
            "source_url": building.source_url,
        }

    def build_catalog_map(self, buildings: list[Building]) -> dict[str, str]:
        catalog_map: dict[str, str] = {}
        for building in buildings:
            if not building.name:
                continue
            normalized_name = normalize_catalog_name(building.name)
            if not normalized_name:
                continue
            existing_id = catalog_map.get(normalized_name)
            if existing_id is not None and existing_id != str(building.id):
                continue
            catalog_map[normalized_name] = str(building.id)
        return catalog_map

    def get_all_buildings_for_tool(self) -> list[dict[str, Any]]:
        return [self._building_list_item(building) for building in self.list_all()]

    def get_all_buildings_and_map_for_tool(self) -> tuple[list[dict[str, Any]], dict[str, str]]:
        buildings = self.list_all()
        return [self._building_list_item(building) for building in buildings], self.build_catalog_map(
            buildings
        )

    def get_building_id_by_name_for_tool(self, name: str) -> str | None:
        _, catalog_map = self.get_all_buildings_and_map_for_tool()
        return catalog_map.get(normalize_catalog_name(name))

    def get_building_by_tool_id(self, building_id: uuid.UUID | str) -> Building | None:
        return self.get(_coerce_building_id(building_id))

    def serialize_building_info_for_tool(self, building: Building) -> dict[str, Any]:
        return {
            "building_id": str(building.id),
            "building_info": {
                "name": building.name,
                "information": building.information or "",
                "source_url": building.source_url,
                "extraction_version": building.extraction_version,
            },
            # URLs are intentionally omitted: the model must call send_photo_file,
            # send_video_file or send_building_document to deliver media to the user.
            "building_photos_total": len(building.photos_url or []),
            "building_videos_total": len(building.videos_url or []),
            "building_documents_total": len(building.documents_url or []),
        }

    def get_building_info_for_tool(
        self, building_id: uuid.UUID | str
    ) -> dict[str, Any] | None:
        building = self.get_building_by_tool_id(building_id)
        if building is None:
            return None
        return self.serialize_building_info_for_tool(building)
