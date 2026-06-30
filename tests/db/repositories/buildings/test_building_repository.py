"""BuildingRepository coverage: CRUD, JSONB roundtrip, and tool helpers."""

from uuid import uuid4

from sqlmodel import Session

from app.db.models import Building, BuildingUpdate
from app.db.repositories import BuildingRepository
from app.db.repositories.buildings import normalize_catalog_name

from .factories import build_building_create, make_building


class TestCrud:
    def test_create_get_list_update_delete_roundtrip(self, db_session: Session) -> None:
        repo = BuildingRepository(db_session)
        created = repo.create(build_building_create(name="Residencial Aurora"))

        assert created.id is not None
        assert repo.get(created.id) is not None
        assert [building.name for building in repo.list_all()] == ["Residencial Aurora"]

        before_updated_at = created.updated_at
        updated = repo.update(
            BuildingUpdate(
                id=created.id,
                name="Residencial Aurora II",
                extraction_version="v2",
                photos_url=["https://cdn.example.com/buildings/aurora/new.jpg"],
            )
        )

        assert updated.id == created.id
        assert updated.name == "Residencial Aurora II"
        assert updated.extraction_version == "v2"
        assert updated.updated_at >= before_updated_at

        repo.delete(updated)
        db_session.flush()

        assert repo.get(created.id) is None


class TestJsonRoundtrip:
    def test_jsonb_payloads_survive_flush_and_reload(self, db_session: Session) -> None:
        created = make_building(
            db_session,
            information="Penthouse com vista panoramica e acabamento premium.",
        )
        db_session.expire_all()

        reloaded = db_session.get(Building, created.id)
        assert reloaded is not None
        assert reloaded.information == "Penthouse com vista panoramica e acabamento premium."
        assert reloaded.photos_url == [
            "https://cdn.example.com/buildings/aurora/fachada.jpg",
            "https://cdn.example.com/buildings/aurora/piscina.jpg",
        ]


class TestToolHelpers:
    def test_catalog_helpers_return_consistent_ids_and_maps(
        self, db_session: Session
    ) -> None:
        first = make_building(db_session, name="Residencial Aurora")
        second = make_building(db_session, name="Residencial Áurora")

        repo = BuildingRepository(db_session)
        catalog_map = repo.build_catalog_map([first, second])

        assert catalog_map["residencial aurora"] == str(first.id)
        assert catalog_map["residencial aurora"] != str(second.id)
        assert normalize_catalog_name("Residencial Áurora") == "residencial aurora"

        building_list = repo.get_all_buildings_for_tool()
        assert {item["building_name"] for item in building_list} == {
            "Residencial Aurora",
            "Residencial Áurora",
        }
        assert {
            item["building_id"] for item in building_list
        } == {str(first.id), str(second.id)}

    def test_get_building_info_for_tool_returns_serialized_payload(
        self, db_session: Session
    ) -> None:
        building = make_building(db_session)
        repo = BuildingRepository(db_session)

        payload = repo.get_building_info_for_tool(building.id)

        assert payload is not None
        assert payload["building_id"] == str(building.id)
        assert payload["building_info"]["name"] == building.name
        assert payload["building_info"]["information"] == (
            "Empreendimento premium com áreas de lazer, boa localização e "
            "unidades modernas."
        )
        assert payload["building_photos_total"] == 2
        assert payload["building_videos_total"] == 1
        assert payload["building_documents_total"] == 1
        assert payload["media_inventory"] == {
            "photos": ["fachada.jpg", "piscina.jpg"],
            "videos": ["tour.mp4"],
            "documents": ["aurora.pdf"],
        }

    def test_get_building_info_for_tool_returns_none_for_unknown_id(
        self, db_session: Session
    ) -> None:
        repo = BuildingRepository(db_session)

        assert repo.get_building_info_for_tool(uuid4()) is None
