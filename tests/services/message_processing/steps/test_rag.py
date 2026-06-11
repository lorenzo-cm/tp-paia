"""Pin the RAG step seam around the catalog retrieval context."""

from types import SimpleNamespace

import pytest

from app.services.message_processing.schemas import Enriched
from app.services.message_processing.steps.rag import rag_index
from app.services.real_estate_rag.store import reset_in_memory_collections


def setup_function() -> None:
    reset_in_memory_collections()


def teardown_function() -> None:
    reset_in_memory_collections()


def test_rag_index_populates_context_field_without_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeService:
        def build_context(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            return []

    monkeypatch.setattr(
        "app.services.message_processing.steps.rag.get_building_rag_service",
        lambda: _FakeService(),
    )

    enriched = Enriched(combined_text="anything", agent_attachments=[])
    repos = SimpleNamespace(building=SimpleNamespace(db=None))

    result = rag_index(enriched, repos)

    assert result is enriched
    assert result.rag_context == []


def test_rag_index_accepts_empty_enriched() -> None:
    repos = SimpleNamespace(building=SimpleNamespace(db=None))

    result = rag_index(Enriched(combined_text="", agent_attachments=[]), repos)

    assert result.rag_context == []
