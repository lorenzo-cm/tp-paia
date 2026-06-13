from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session

from app.core.config import get_settings
from app.db.models import Building
from app.services.real_estate_rag.factory import get_building_rag_service

settings = get_settings()


def _auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        f"{settings.API_PREFIX}/auth/token",
        data={"username": "user@example.com", "password": "123456"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _truncate_buildings(db_engine) -> None:
    with Session(db_engine) as db:
        db.exec(text("TRUNCATE buildings RESTART IDENTITY CASCADE"))  # type: ignore[call-overload]
        db.commit()


def test_admin_create_list_update_and_search_buildings(
    client: TestClient,
    db_engine,
    monkeypatch,
) -> None:
    _truncate_buildings(db_engine)
    monkeypatch.setattr("app.api.deps.engine", db_engine)
    monkeypatch.setattr("app.db.config.engine", db_engine)
    get_building_rag_service.cache_clear()
    headers = _auth_headers(client)

    create_response = client.post(
        f"{settings.API_PREFIX}/v1/admin/buildings",
        headers=headers,
        json={
            "name": "Residencial Aurora",
            "information": "Lazer completo, varanda gourmet e plantas de 2 quartos.",
            "photos_url": ["https://cdn.example.com/aurora/fachada.jpg"],
            "videos_url": ["https://cdn.example.com/aurora/tour.mp4"],
            "documents_url": ["https://cdn.example.com/aurora/book.pdf"],
            "source_url": "https://example.com/aurora",
            "extraction_version": "v1",
        },
    )
    assert create_response.status_code == 201
    building_id = create_response.json()["building"]["id"]

    list_response = client.get(f"{settings.API_PREFIX}/v1/admin/buildings", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["items"][0]["building_id"] == building_id

    update_response = client.put(
        f"{settings.API_PREFIX}/v1/admin/buildings/{building_id}",
        headers=headers,
        json={"information": "Lazer completo, rooftop e plantas de 2 quartos."},
    )
    assert update_response.status_code == 200
    assert "rooftop" in update_response.json()["building"]["information"]

    search_response = client.get(
        f"{settings.API_PREFIX}/v1/admin/rag/search",
        headers=headers,
        params={"query": "rooftop", "building_id": building_id},
    )
    assert search_response.status_code == 200
    assert search_response.json()["matches"][0]["building_id"] == building_id

    with Session(db_engine) as db:
        building = db.get(Building, building_id)
        assert building is not None
        assert "rooftop" in building.information


def test_admin_reindex_all_requires_auth(client: TestClient) -> None:
    response = client.post(f"{settings.API_PREFIX}/v1/admin/buildings/reindex-all")
    assert response.status_code == 401
