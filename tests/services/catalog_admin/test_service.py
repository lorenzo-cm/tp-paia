from sqlalchemy import text
from sqlmodel import Session

from app.db.models import BuildingCreate
from app.services.catalog_admin import CatalogAdminService
from app.services.real_estate_rag.factory import get_building_rag_service
from app.services.real_estate_rag.store import reset_in_memory_collections


def test_reindex_all_and_search(db_engine, monkeypatch) -> None:
    reset_in_memory_collections()
    with Session(db_engine) as db:
        db.exec(text("TRUNCATE buildings RESTART IDENTITY CASCADE"))  # type: ignore[call-overload]
        db.commit()
    monkeypatch.setattr("app.db.config.engine", db_engine)
    get_building_rag_service.cache_clear()
    with Session(db_engine) as db:
        service = CatalogAdminService.from_session(db, get_building_rag_service())
        building, _ = service.create_building(
            BuildingCreate(
                name="Mirante das Palmeiras",
                information="Coworking, varanda e lazer no rooftop.",
                photos_url=[],
                videos_url=[],
                documents_url=[],
                source_url="https://example.com/mirante",
                extraction_version="v1",
            )
        )
        db.commit()
        summary = service.reindex_all()
        assert summary.requested == 1
        result = service.rag_search(query="rooftop", building_id=building.id)
        assert result["matches"][0]["building_id"] == str(building.id)
