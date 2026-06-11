from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.core.config import get_settings
from app.db.models import Building
from app.services.real_estate_rag.embeddings import (
    EmbeddingProvider,
    get_embedding_provider,
)
from app.services.real_estate_rag.schemas import RagHit
from app.services.real_estate_rag.store import (
    InMemoryHybridStore,
    QdrantHybridStore,
    StoredPoint,
    VectorStoreBackend,
)


@dataclass(slots=True)
class BuildingRagPayload:
    building_id: str
    building_name: str
    source_url: str | None
    information: str
    extraction_version: str | None = None


def _normalize_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class BuildingRAGService:
    def __init__(
        self,
        *,
        store: VectorStoreBackend,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self._store = store
        self._embeddings = embedding_provider or get_embedding_provider()

    @property
    def collection_name(self) -> str:
        return self._store.collection_name

    @staticmethod
    def chunk_information(
        text: str,
        *,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> list[str]:
        settings = get_settings()
        size = chunk_size or settings.RAG_CHUNK_SIZE
        overlap = chunk_overlap or settings.RAG_CHUNK_OVERLAP
        normalized = _normalize_ws(text)
        if not normalized:
            return []

        sentences = re.split(r"(?<=[.!?])\s+", normalized)
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if not sentence:
                continue
            if len(sentence) > size:
                if current:
                    chunks.append(current.strip())
                    current = ""
                start = 0
                while start < len(sentence):
                    end = min(len(sentence), start + size)
                    chunks.append(sentence[start:end].strip())
                    if end >= len(sentence):
                        break
                    start = max(end - overlap, start + 1)
                continue
            candidate = f"{current} {sentence}".strip() if current else sentence
            if len(candidate) <= size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                current = sentence
        if current:
            chunks.append(current.strip())
        return [chunk for chunk in chunks if chunk]

    def _vectorize(self, texts: list[str]) -> list[list[float]]:
        return self._embeddings.embed_texts(texts)

    def _store_points(self, points: list[StoredPoint]) -> None:
        self._store.ensure_collection()
        self._store.upsert(points)
        self._store.rebuild_lexical_index()

    @staticmethod
    def _serialize_payload(
        payload: BuildingRagPayload,
        *,
        chunk_index: int,
        chunk_text: str,
    ) -> dict[str, Any]:
        return {
            "building_id": payload.building_id,
            "building_name": payload.building_name,
            "source_url": payload.source_url,
            "chunk_index": chunk_index,
            "text": chunk_text,
            "extraction_version": payload.extraction_version,
        }

    def index_building_payload(self, payload: BuildingRagPayload) -> int:
        chunks = self.chunk_information(payload.information)
        self._store.ensure_collection()
        self._store.delete_building(payload.building_id)
        if not chunks:
            self._store.rebuild_lexical_index()
            return 0

        vectors = self._vectorize(chunks)
        points = [
            StoredPoint(
                id=f"{payload.building_id}:{index}",
                vector=vector,
                payload=self._serialize_payload(
                    payload,
                    chunk_index=index,
                    chunk_text=chunk_text,
                ),
            )
            for index, (chunk_text, vector) in enumerate(
                zip(chunks, vectors, strict=True)
            )
        ]
        self._store_points(points)
        return len(points)

    def index_building(self, building: Building) -> int:
        return self.index_building_payload(
            BuildingRagPayload(
                building_id=str(building.id),
                building_name=building.name,
                source_url=building.source_url,
                information=building.information or "",
                extraction_version=building.extraction_version,
            )
        )

    def resolve_building_id(self, query: str, session: Session) -> UUID | None:
        from app.db.repositories.buildings import normalize_catalog_name
        normalized_query = normalize_catalog_name(query)
        if not normalized_query:
            return None
        from app.db.repositories import BuildingRepository

        repo = BuildingRepository(session)
        catalog_map = repo.build_catalog_map(repo.list_all())
        matches = [
            UUID(building_id)
            for normalized_name, building_id in catalog_map.items()
            if normalized_name and normalized_name in normalized_query
        ]
        unique = list({str(match): match for match in matches}.values())
        return unique[0] if len(unique) == 1 else None

    def search(
        self,
        query: str,
        *,
        session: Session | None = None,
        building_id: UUID | str | None = None,
        limit: int | None = None,
    ) -> list[RagHit]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        settings = get_settings()
        resolved_limit = int(limit) if limit is not None else settings.QDRANT_SEARCH_LIMIT
        resolved_building_id: str | None
        if building_id is None and session is not None:
            inferred = self.resolve_building_id(normalized_query, session)
            resolved_building_id = str(inferred) if inferred is not None else None
        elif building_id is None:
            resolved_building_id = None
        else:
            resolved_building_id = str(building_id)

        query_vector = self._vectorize([normalized_query])[0]
        raw_hits = self._store.search(
            query_vector,
            normalized_query,
            building_id=resolved_building_id,
            limit=max(resolved_limit * 2, resolved_limit),
        )
        hits: list[RagHit] = []
        for raw in raw_hits[:resolved_limit]:
            payload = dict(raw["payload"])
            hits.append(
                RagHit(
                    point_id=str(raw["id"]),
                    building_id=str(payload.get("building_id", "")),
                    building_name=str(payload.get("building_name", "")),
                    source_url=payload.get("source_url"),
                    chunk_index=int(payload.get("chunk_index", 0)),
                    text=str(payload.get("text", "")),
                    score=float(raw["score"]),
                )
            )
        return hits

    def render_context(self, hits: list[RagHit]) -> str:
        if not hits:
            return ""
        lines = [
            "Contexto recuperado do catalogo imobiliario:",
        ]
        for index, hit in enumerate(hits, start=1):
            source = f" | fonte: {hit.source_url}" if hit.source_url else ""
            lines.append(
                f"{index}. {hit.building_name} (chunk {hit.chunk_index}, score {hit.score:.3f})"
                f"{source}"
            )
            lines.append(f"   Trecho: {hit.text}")
        return "\n".join(lines)

    def build_context(
        self,
        query: str,
        *,
        session: Session | None = None,
        building_id: UUID | str | None = None,
        limit: int | None = None,
    ) -> list[RagHit]:
        return self.search(
            query,
            session=session,
            building_id=building_id,
            limit=limit,
        )


def create_building_rag_service() -> BuildingRAGService:
    settings = get_settings()
    if settings.QDRANT_URL:
        try:
            store = QdrantHybridStore(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vector_size=settings.QDRANT_VECTOR_SIZE,
                qdrant_url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY,
            )
        except Exception:
            store = InMemoryHybridStore(
                collection_name=settings.QDRANT_COLLECTION_NAME,
                vector_size=settings.QDRANT_VECTOR_SIZE,
            )
    else:
        store = InMemoryHybridStore(
            collection_name=settings.QDRANT_COLLECTION_NAME,
            vector_size=settings.QDRANT_VECTOR_SIZE,
        )
    return BuildingRAGService(store=store)
