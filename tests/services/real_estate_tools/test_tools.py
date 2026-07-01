from itertools import count
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlmodel import Session

import app.services.real_estate_tools.tools as tools_module
from app.db.models import BuildingCreate
from app.db.repositories import BuildingRepository
from app.db.repositories.buildings import normalize_catalog_name
from app.services.real_estate_rag.store import reset_in_memory_collections
from app.services.real_estate_tools import (
    REAL_ESTATE_TOOL_REGISTRY,
    REAL_ESTATE_TOOLS,
    get_all_building,
    get_building_info,
    search_building_information,
    send_building_document,
    send_photo_file,
    send_video_file,
    set_lead_quality,
    store_lead_house,
    transfer_human,
)

_source_counter = count(1)


@pytest.fixture(autouse=True)
def _reset_rag_index() -> None:
    reset_in_memory_collections()
    yield
    reset_in_memory_collections()


@pytest.fixture(autouse=True)
def _truncate_buildings(db_engine) -> None:
    with Session(db_engine) as db:
        db.exec(text("TRUNCATE buildings RESTART IDENTITY CASCADE"))  # type: ignore[call-overload]
        db.commit()


def _seed_building(db_engine, **overrides):
    source_url = overrides.pop(
        "source_url", f"https://example.com/aurora/{next(_source_counter)}"
    )
    with Session(db_engine) as db:
        repo = BuildingRepository(db)
        data = {
            "name": "Residencial Aurora",
            "information": "Empreendimento de alto padrão com lazer completo.",
            "photos_url": [
                "https://cdn.example.com/aurora/fachada-01.jpg",
                "https://cdn.example.com/aurora/fachada-02.jpg",
                "https://cdn.example.com/aurora/piscina.jpg",
            ],
            "videos_url": [
                "https://cdn.example.com/aurora/tour.mp4",
                "https://cdn.example.com/aurora/apresentacao.mp4",
            ],
            "documents_url": [
                "https://cdn.example.com/aurora/memorial.pdf",
                "https://cdn.example.com/aurora/brochure.pdf",
            ],
            "source_url": source_url,
            "extraction_version": "v1",
            **overrides,
        }
        building = repo.create(
            BuildingCreate(**data)
        )
        db.commit()
        db.refresh(building)
        return building


def _definition(name: str) -> dict:
    return next(tool for tool in REAL_ESTATE_TOOLS if tool["name"] == name)


def test_tool_definitions_have_expected_names_and_fields() -> None:
    names = [tool["name"] for tool in REAL_ESTATE_TOOLS]
    assert names == [
        "get_all_building",
        "get_building_info",
        "search_building_information",
        "send_photo_file",
        "send_video_file",
        "send_building_document",
        "store_lead_house",
        "transfer_human",
        "set_lead_quality",
    ]
    assert _definition("get_building_info")["parameters"]["required"] == ["building_id"]
    assert _definition("send_photo_file")["parameters"]["required"] == [
        "building_id",
        "parte_do_imovel",
    ]
    assert _definition("send_video_file")["parameters"]["required"] == [
        "building_id",
        "video_file_name",
    ]
    assert _definition("send_building_document")["parameters"]["required"] == [
        "building_id",
        "document_file_name",
    ]
    assert _definition("store_lead_house")["parameters"]["required"] == ["building_id"]
    assert _definition("transfer_human")["parameters"]["required"] == [
        "summary",
        "email",
        "lead_quality",
        "qualification_reason",
    ]


def test_tool_registry_contains_all_real_tools() -> None:
    assert set(REAL_ESTATE_TOOL_REGISTRY) == {
        "get_all_building",
        "get_building_info",
        "search_building_information",
        "send_photo_file",
        "send_video_file",
        "send_building_document",
        "store_lead_house",
        "transfer_human",
        "set_lead_quality",
    }


def test_get_all_building_reads_live_catalog(db_engine, monkeypatch) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = get_all_building()

    assert result["success"] is True
    assert result["tool_output"]["building_list"] == [
        {
            "building_id": str(building.id),
            "building_name": "Residencial Aurora",
            "source_url": building.source_url,
        }
    ]
    assert result["tool_output"]["building_map"] == {
        normalize_catalog_name("Residencial Aurora"): str(building.id)
    }


def test_get_building_info_returns_serialized_payload(db_engine, monkeypatch) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = get_building_info(building_id=str(building.id))

    assert result["success"] is True
    assert result["tool_output"]["building_id"] == str(building.id)
    assert result["tool_output"]["building_info"]["name"] == "Residencial Aurora"
    assert result["tool_output"]["building_info"]["information"] == (
        "Empreendimento de alto padrão com lazer completo."
    )
    assert result["tool_output"]["building_photos_total"] == 3
    assert result["tool_output"]["building_videos_total"] == 2
    assert result["tool_output"]["building_documents_total"] == 2


def test_get_building_info_accepts_building_name_and_slug(
    db_engine, monkeypatch
) -> None:
    building = _seed_building(db_engine, name="Casa Mirante das Palmeiras")
    monkeypatch.setattr(tools_module, "engine", db_engine)

    by_name = get_building_info(building_id="Casa Mirante das Palmeiras")
    by_slug = get_building_info(building_id="casa_mirante_das_palmeiras")

    assert by_name["success"] is True
    assert by_name["tool_output"]["building_id"] == str(building.id)
    assert by_name["tool_output"]["resolved_from"] == "name"
    assert by_slug["success"] is True
    assert by_slug["tool_output"]["building_id"] == str(building.id)
    assert by_slug["tool_output"]["resolved_from"] in {"name", "slug"}


def test_search_building_information_returns_relevant_chunks(
    db_engine, monkeypatch
) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = search_building_information(query="lazer completo", limit=3)

    assert result["success"] is True
    assert result["tool_output"]["query"] == "lazer completo"
    assert result["tool_output"]["building_id"] is None
    assert result["tool_output"]["matches"][0]["building_id"] == str(building.id)
    assert "lazer completo" in result["tool_output"]["matches"][0]["text"]
    assert "Contexto recuperado" in result["tool_output"]["context"]


def test_get_building_info_returns_not_found_for_unknown_id(
    db_engine, monkeypatch
) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = get_building_info(building_id=str(uuid4()))

    assert result["success"] is False
    assert result["tool_output"]["error_code"] == "building_not_found"
    assert "Nao invente building_id" in result["tool_output"]["retry_instruction"]
    assert result["tool_output"]["available_buildings"] == [
        {
            "building_id": str(building.id),
            "building_name": "Residencial Aurora",
        }
    ]


def test_send_photo_file_selects_up_to_two_matching_urls(db_engine, monkeypatch) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = send_photo_file(building_id=str(building.id), parte_do_imovel="fachada")

    assert result["success"] is True
    assert result["tool_output"]["building_id"] == str(building.id)
    assert result["tool_output"]["parte_do_imovel"] == "fachada"
    assert result["tool_output"]["photos_url"] == [
        "https://cdn.example.com/aurora/fachada-01.jpg",
        "https://cdn.example.com/aurora/fachada-02.jpg",
    ]


def test_send_photo_file_accepts_ordinal_building_reference(
    db_engine, monkeypatch
) -> None:
    _seed_building(db_engine, name="Brisa do Mar Residence")
    _seed_building(db_engine, name="Casa Mirante das Palmeiras")
    aurora = _seed_building(db_engine, name="Residencial Aurora")
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = send_photo_file(building_id="3", parte_do_imovel="piscina")

    assert result["success"] is True
    assert result["tool_output"]["building_id"] == str(aurora.id)
    assert result["tool_output"]["resolved_from"] == "ordinal"
    assert result["tool_output"]["photos_url"] == [
        "https://cdn.example.com/aurora/piscina.jpg"
    ]


def test_send_video_and_document_return_requested_media(
    db_engine, monkeypatch
) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    video = send_video_file(building_id=str(building.id), video_file_name="tour.mp4")
    document = send_building_document(
        building_id=str(building.id), document_file_name="memorial.pdf"
    )

    assert video["success"] is True
    assert video["tool_output"]["video_url"] == "https://cdn.example.com/aurora/tour.mp4"
    assert document["success"] is True
    assert document["tool_output"]["document_url"] == "https://cdn.example.com/aurora/memorial.pdf"


def test_send_video_accepts_name_building_reference(db_engine, monkeypatch) -> None:
    building = _seed_building(db_engine, name="Casa Mirante das Palmeiras")
    monkeypatch.setattr(tools_module, "engine", db_engine)

    video = send_video_file(
        building_id="Casa Mirante das Palmeiras", video_file_name="tour.mp4"
    )

    assert video["success"] is True
    assert video["tool_output"]["building_id"] == str(building.id)
    assert video["tool_output"]["resolved_from"] == "name"
    assert video["tool_output"]["video_url"] == "https://cdn.example.com/aurora/tour.mp4"


def test_send_video_and_document_match_by_partial_name(
    db_engine, monkeypatch
) -> None:
    """An exact name is preferred, but a partial/approximate name (e.g. without the
    extension) still resolves to the right file via substring matching."""
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    video = send_video_file(building_id=str(building.id), video_file_name="tour")
    document = send_building_document(
        building_id=str(building.id), document_file_name="memorial"
    )

    assert video["success"] is True
    assert video["tool_output"]["video_url"] == "https://cdn.example.com/aurora/tour.mp4"
    assert document["success"] is True
    assert (
        document["tool_output"]["document_url"]
        == "https://cdn.example.com/aurora/memorial.pdf"
    )


def test_send_video_reports_available_when_name_does_not_match(
    db_engine, monkeypatch
) -> None:
    """A name that matches nothing must NOT send an arbitrary file; it returns the
    available options so the model can retry with a real name."""
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    video = send_video_file(
        building_id=str(building.id), video_file_name="inexistente.mp4"
    )

    assert video["success"] is False
    assert video["tool_output"]["error_code"] == "media_not_found"
    assert video["tool_output"]["available"] == ["tour.mp4", "apresentacao.mp4"]
    assert "video_url" not in video["tool_output"]


def test_send_video_returns_media_not_found_when_building_has_no_video(
    db_engine, monkeypatch
) -> None:
    with Session(db_engine) as db:
        building = BuildingRepository(db).create(
            BuildingCreate(
                name="Sem Video",
                information="Empreendimento sem video.",
                photos_url=["https://cdn.example.com/sem-video/fachada.jpg"],
                videos_url=[],
                documents_url=[],
                source_url=f"https://example.com/sem-video/{next(_source_counter)}",
                extraction_version="v1",
            )
        )
        db.commit()
        db.refresh(building)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    video = send_video_file(building_id=str(building.id), video_file_name="tour.mp4")

    assert video["success"] is False
    assert video["tool_output"]["error_code"] == "media_not_found"
    assert video["tool_output"]["available"] == []


def test_store_lead_house_registers_interest_payload(db_engine, monkeypatch) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = store_lead_house(building_id=str(building.id))

    assert result["success"] is True
    assert result["tool_output"]["status"] == "lead_interest_registered"
    assert result["integration_payload"] == {
        "lead_interest": {
            "building_id": str(building.id),
            "building_name": "Residencial Aurora",
            "source_url": building.source_url,
        }
    }


def test_transfer_human_returns_valid_structure_when_complete() -> None:
    result = transfer_human(
        summary="Lead quer atendimento humano",
        email="lead@example.com",
        lead_quality="high",
        qualification_reason="Quer visita e avancou na negociacao.",
    )
    assert result == {
        "success": True,
        "tool_output": {
            "type": "transfer_human",
            "message": "Transferindo para atendente humano...",
            "summary": "Lead quer atendimento humano",
            "email": "lead@example.com",
            "lead_quality": "high",
            "qualification_reason": "Quer visita e avancou na negociacao.",
        },
        "summary": "",
    }


def test_transfer_human_requires_summary() -> None:
    result = transfer_human(
        email="lead@example.com",
        lead_quality="medium",
        qualification_reason="Pediu visita.",
    )
    assert result["success"] is False
    assert result["tool_output"]["error_code"] == "missing_required_fields"
    assert result["tool_output"]["missing_fields"] == ["summary"]


def test_transfer_human_rejects_invalid_lead_quality() -> None:
    result = transfer_human(
        summary="Lead quer visita",
        email="lead@example.com",
        lead_quality="urgent",
        qualification_reason="Pediu visita.",
    )
    assert result["success"] is False
    assert result["tool_output"]["error_code"] == "invalid_lead_quality"


def test_store_lead_house_rejects_invalid_building_id(db_engine, monkeypatch) -> None:
    building = _seed_building(db_engine)
    monkeypatch.setattr(tools_module, "engine", db_engine)

    result = store_lead_house(building_id="abc")
    assert result["success"] is False
    assert result["tool_output"]["error_code"] == "invalid_building_id"
    assert result["tool_output"]["building_id"] == "abc"
    assert "Nao invente building_id" in result["tool_output"]["retry_instruction"]
    assert result["tool_output"]["available_buildings"] == [
        {
            "building_id": str(building.id),
            "building_name": "Residencial Aurora",
        }
    ]


def test_set_lead_quality_returns_valid_structure_when_complete() -> None:
    result = set_lead_quality(
        lead_quality="High",
        qualification_reason="Lead engajado e com interesse claro.",
    )
    assert result == {
        "success": True,
        "tool_output": {
            "type": "set_lead_quality",
            "lead_quality": "high",
            "qualification_reason": "Lead engajado e com interesse claro.",
            "status": "lead_quality_registered",
        },
        "summary": "Qualificacao do lead registrada.",
    }


def test_set_lead_quality_requires_qualification_reason() -> None:
    result = set_lead_quality(lead_quality="medium")
    assert result["success"] is False
    assert result["tool_output"]["error_code"] == "missing_required_fields"
    assert result["tool_output"]["missing_fields"] == ["qualification_reason"]


def test_set_lead_quality_rejects_invalid_lead_quality() -> None:
    result = set_lead_quality(
        lead_quality="urgent",
        qualification_reason="Pediu visita.",
    )
    assert result["success"] is False
    assert result["tool_output"]["error_code"] == "invalid_lead_quality"
