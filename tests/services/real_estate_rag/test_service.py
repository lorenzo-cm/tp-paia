from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

import pytest

from app.services.real_estate_rag.schemas import RagHit
from app.services.real_estate_rag.service import (
    BuildingRagPayload,
    BuildingRAGService,
)
from app.services.real_estate_rag.store import (
    InMemoryHybridStore,
    _tokenize,
    reset_in_memory_collections,
)


@dataclass(slots=True)
class FakeEmbeddings:
    model_name: str = "fake"
    vector_size: int = 3

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            lowered = text.lower()
            if "piscina" in lowered:
                vectors.append([1.0, 0.0, 0.0])
            elif "academia" in lowered:
                vectors.append([0.0, 1.0, 0.0])
            else:
                vectors.append([0.0, 0.0, 1.0])
        return vectors


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    reset_in_memory_collections()
    yield
    reset_in_memory_collections()


def _service() -> BuildingRAGService:
    return BuildingRAGService(
        store=InMemoryHybridStore(collection_name="test", vector_size=3),
        embedding_provider=FakeEmbeddings(),
    )


def test_chunk_information_splits_long_text() -> None:
    text = " ".join(["Apartamento com piscina e academia." for _ in range(40)])
    chunks = BuildingRAGService.chunk_information(text, chunk_size=120, chunk_overlap=20)

    assert len(chunks) > 1
    assert all(chunk for chunk in chunks)
    assert all(len(chunk) <= 120 for chunk in chunks)


def test_bm25_tokenization_normalizes_accents_and_punctuation() -> None:
    assert _tokenize("ÁREA 2 dormitórios, suíte!") == [
        "area",
        "2",
        "dormitorios",
        "suite",
    ]


def test_index_and_search_respects_building_filter() -> None:
    service = _service()
    aurora_id = str(uuid4())
    luna_id = str(uuid4())

    service.index_building_payload(
        BuildingRagPayload(
            building_id=aurora_id,
            building_name="Residencial Aurora",
            source_url="https://example.com/aurora",
            information="Empreendimento com piscina e lazer completo.",
        )
    )
    service.index_building_payload(
        BuildingRagPayload(
            building_id=luna_id,
            building_name="Residencial Luna",
            source_url="https://example.com/luna",
            information="Projeto com academia e coworking.",
        )
    )

    global_hits = service.search("piscina", limit=3)
    filtered_hits = service.search("piscina", building_id=aurora_id, limit=3)

    assert global_hits[0].building_id == aurora_id
    assert filtered_hits[0].building_id == aurora_id
    assert all(hit.building_id == aurora_id for hit in filtered_hits)
    assert isinstance(global_hits[0], RagHit)


def test_reindex_replaces_previous_chunks() -> None:
    service = _service()
    building_id = str(uuid4())

    service.index_building_payload(
        BuildingRagPayload(
            building_id=building_id,
            building_name="Residencial Aurora",
            source_url="https://example.com/aurora",
            information="Texto antigo sobre piscina.",
        )
    )
    service.index_building_payload(
        BuildingRagPayload(
            building_id=building_id,
            building_name="Residencial Aurora",
            source_url="https://example.com/aurora",
            information="Texto novo sobre academia.",
        )
    )

    old_hits = service.search("piscina", building_id=building_id, limit=3)
    new_hits = service.search("academia", building_id=building_id, limit=3)

    assert old_hits == []
    assert new_hits[0].building_id == building_id


def test_hybrid_search_ranks_rare_term_above_generic_chunk() -> None:
    service = _service()
    generic_id = str(uuid4())
    rare_id = str(uuid4())

    service.index_building_payload(
        BuildingRagPayload(
            building_id=generic_id,
            building_name="Residencial Genérico",
            source_url=None,
            information="Apartamento com piscina e lazer completo.",
        )
    )
    service.index_building_payload(
        BuildingRagPayload(
            building_id=rare_id,
            building_name="Residencial Aurora",
            source_url=None,
            information="Planta com sauna tripla e hall exclusivo.",
        )
    )

    hits = service.search("sauna tripla", limit=3)

    assert hits[0].building_id == rare_id


def test_reindex_refreshes_bm25_when_new_building_enters_catalog() -> None:
    service = _service()
    first_id = str(uuid4())
    second_id = str(uuid4())

    service.index_building_payload(
        BuildingRagPayload(
            building_id=first_id,
            building_name="Residencial Mar",
            source_url=None,
            information="Apartamento com piscina e vista para o mar.",
        )
    )

    before_hits = service.search("sauna tripla", limit=3)
    assert before_hits == []

    service.index_building_payload(
        BuildingRagPayload(
            building_id=second_id,
            building_name="Residencial Aurora",
            source_url=None,
            information="Planta com sauna tripla e hall exclusivo.",
        )
    )

    after_hits = service.search("sauna tripla", limit=3)

    assert after_hits[0].building_id == second_id
    assert after_hits[0].text == "Planta com sauna tripla e hall exclusivo."


def test_search_uses_extracted_information_text() -> None:
    service = _service()
    building_id = str(uuid4())

    service.index_building_payload(
        BuildingRagPayload(
            building_id=building_id,
            building_name="Residencial Documento",
            source_url="https://example.com/documento.pdf",
            information="Conteudo extraido do PDF com varanda gourmet e deposito.",
        )
    )

    hits = service.search("varanda gourmet deposito", limit=3)

    assert hits[0].building_id == building_id
    assert hits[0].source_url == "https://example.com/documento.pdf"
