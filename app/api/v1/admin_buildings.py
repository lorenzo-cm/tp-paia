from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import SessionDep
from app.api.v1.schemas.buildings import BuildingCreateRequest, BuildingUpdateRequest
from app.core.auth import get_current_user
from app.core.auth.fake_users import FakeUser
from app.db.models import BuildingUpdate
from app.services.catalog_admin import CatalogAdminService
from app.services.real_estate_rag.factory import get_building_rag_service

router = APIRouter(prefix="/admin", tags=["admin-buildings"])


def _service(db: SessionDep) -> CatalogAdminService:
    return CatalogAdminService.from_session(db, get_building_rag_service())


@router.get("/buildings")
def list_buildings(
    db: SessionDep,
    _: FakeUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = _service(db)
    return {"items": service.list_buildings(), "rag_status": service.rag_status()}


@router.get("/buildings/{building_id}")
def get_building(
    building_id: UUID,
    db: SessionDep,
    _: FakeUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = _service(db)
    building = service.get_building(building_id)
    if building is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    return building.model_dump()


@router.post("/buildings", status_code=status.HTTP_201_CREATED)
def create_building(
    payload: BuildingCreateRequest,
    db: SessionDep,
    _: FakeUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = _service(db)
    building, scheduled = service.create_building(payload)
    db.commit()
    db.refresh(building)
    return {
        "status": "created",
        "indexation": "scheduled" if scheduled else "not_scheduled",
        "building": building.model_dump(),
    }


@router.put("/buildings/{building_id}")
def update_building(
    building_id: UUID,
    payload: BuildingUpdateRequest,
    db: SessionDep,
    _: FakeUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = _service(db)
    if service.get_building(building_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    building, scheduled = service.update_building(
        building_id,
        BuildingUpdate(id=building_id, **payload.model_dump(exclude_unset=True)),
    )
    db.commit()
    db.refresh(building)
    return {
        "status": "updated",
        "indexation": "scheduled" if scheduled else "not_scheduled",
        "building": building.model_dump(),
    }


@router.post("/buildings/{building_id}/reindex")
def reindex_building(
    building_id: UUID,
    db: SessionDep,
    _: FakeUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = _service(db)
    if not service.reindex_building(building_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Building not found")
    return {"status": "scheduled", "building_id": str(building_id)}


@router.post("/buildings/reindex-all")
def reindex_all_buildings(
    db: SessionDep,
    _: FakeUser = Depends(get_current_user),
) -> dict[str, Any]:
    service = _service(db)
    summary = service.reindex_all()
    return {
        "status": "scheduled",
        "requested": summary.requested,
        "building_ids": summary.building_ids,
    }


@router.get("/rag/search")
def rag_search(
    db: SessionDep,
    _: FakeUser = Depends(get_current_user),
    query: str = Query(..., min_length=1),
    building_id: UUID | None = None,
    limit: int = Query(5, ge=1, le=10),
) -> dict[str, Any]:
    service = _service(db)
    return service.rag_search(query=query, building_id=building_id, limit=limit)
