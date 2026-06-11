from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from math import sqrt
from typing import Any, Protocol

import numpy as np
from bm25s import BM25

from app.core.config import get_settings


@dataclass(slots=True)
class StoredPoint:
    id: str
    vector: list[float]
    payload: dict[str, Any]


class VectorStoreBackend(Protocol):
    collection_name: str
    vector_size: int

    def ensure_collection(self) -> None: ...

    def delete_building(self, building_id: str) -> None: ...

    def upsert(self, points: list[StoredPoint]) -> None: ...

    def iter_points(self) -> list[StoredPoint]: ...

    def rebuild_lexical_index(self) -> None: ...

    def search(
        self,
        query_vector: list[float],
        query_text: str,
        *,
        building_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower()


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(_normalize_text(text))


def _min_max_scale(values: np.ndarray) -> np.ndarray:
    if values.size == 0:
        return values
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if maximum == minimum:
        if maximum <= 0:
            return np.zeros_like(values, dtype="float32")
        return np.ones_like(values, dtype="float32")
    return (values - minimum) / (maximum - minimum)


def _normalized_weights() -> tuple[float, float]:
    settings = get_settings()
    dense_weight = float(settings.RAG_DENSE_WEIGHT)
    lexical_weight = float(settings.RAG_BM25_WEIGHT)
    total = dense_weight + lexical_weight
    if total <= 0:
        return 1.0, 0.0
    return dense_weight / total, lexical_weight / total


def _point_vector(vector: Any) -> list[float]:
    if isinstance(vector, dict):
        if not vector:
            return []
        first_vector = next(iter(vector.values()))
        return [float(value) for value in first_vector]
    return [float(value) for value in vector or []]


@dataclass(slots=True)
class _HybridSnapshot:
    points: list[StoredPoint]
    lexical_index: BM25 | None

    @classmethod
    def build(cls, points: list[StoredPoint]) -> _HybridSnapshot:
        if not points:
            return cls(points=[], lexical_index=None)

        tokenized_corpus = [_tokenize(str(point.payload.get("text", ""))) for point in points]
        lexical_index = BM25(backend="numpy", csc_backend="numpy")
        lexical_index.index(tokenized_corpus, show_progress=False, leave_progress=False)
        return cls(points=points, lexical_index=lexical_index)


def _build_ranked_results(
    all_points: list[StoredPoint],
    lexical_index: BM25 | None,
    query_vector: list[float],
    query_text: str,
    *,
    building_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    if not all_points:
        return []

    points = all_points
    if building_id is not None:
        points = [
            point
            for point in all_points
            if str(point.payload.get("building_id")) == str(building_id)
        ]
    if not points:
        return []

    dense_scores = np.asarray(
        [_cosine(query_vector, point.vector) for point in points], dtype="float32"
    )
    lexical_scores = np.zeros(len(points), dtype="float32")
    query_tokens = _tokenize(query_text)
    if lexical_index is not None and query_tokens:
        all_points_by_id = {point.id: index for index, point in enumerate(all_points)}
        all_lexical_scores = np.asarray(
            lexical_index.get_scores(query_tokens), dtype="float32"
        )
        lexical_scores = np.asarray(
            [
                all_lexical_scores[all_points_by_id[point.id]]
                if point.id in all_points_by_id
                else 0.0
                for point in points
            ],
            dtype="float32",
        )

    dense_scores = _min_max_scale(dense_scores)
    lexical_scores = _min_max_scale(lexical_scores)
    dense_weight, lexical_weight = _normalized_weights()

    ranked: list[dict[str, Any]] = []
    for point, dense_score, lexical_score in zip(
        points, dense_scores, lexical_scores, strict=True
    ):
        score = (float(dense_score) * dense_weight) + (
            float(lexical_score) * lexical_weight
        )
        if score <= 0.0:
            continue
        ranked.append({"id": point.id, "score": score, "payload": point.payload})

    ranked.sort(key=lambda item: (item["score"], item["id"]), reverse=True)
    return ranked[:limit]


class InMemoryHybridStore:
    _collections: dict[str, dict[str, StoredPoint]] = {}

    def __init__(self, *, collection_name: str, vector_size: int) -> None:
        self.collection_name = collection_name
        self.vector_size = vector_size
        self._snapshot = _HybridSnapshot(points=[], lexical_index=None)

    def ensure_collection(self) -> None:
        self._collections.setdefault(self.collection_name, {})

    def delete_building(self, building_id: str) -> None:
        collection = self._collections.setdefault(self.collection_name, {})
        ids_to_delete = [
            point_id
            for point_id, point in collection.items()
            if str(point.payload.get("building_id")) == str(building_id)
        ]
        for point_id in ids_to_delete:
            del collection[point_id]

    def upsert(self, points: list[StoredPoint]) -> None:
        collection = self._collections.setdefault(self.collection_name, {})
        for point in points:
            collection[point.id] = point

    def iter_points(self) -> list[StoredPoint]:
        collection = self._collections.setdefault(self.collection_name, {})
        return sorted(collection.values(), key=lambda point: point.id)

    def rebuild_lexical_index(self) -> None:
        self._snapshot = _HybridSnapshot.build(self.iter_points())

    def search(
        self,
        query_vector: list[float],
        query_text: str,
        *,
        building_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        snapshot = self._snapshot
        if not snapshot.points:
            self.rebuild_lexical_index()
            snapshot = self._snapshot
        return _build_ranked_results(
            snapshot.points,
            snapshot.lexical_index,
            query_vector,
            query_text,
            building_id=building_id,
            limit=limit,
        )


def reset_in_memory_collections() -> None:
    InMemoryHybridStore._collections.clear()


class QdrantHybridStore:
    def __init__(
        self,
        *,
        collection_name: str,
        vector_size: int,
        qdrant_url: str,
        api_key: str | None = None,
    ) -> None:
        from qdrant_client import QdrantClient

        self.collection_name = collection_name
        self.vector_size = vector_size
        self._client = QdrantClient(url=qdrant_url, api_key=api_key)
        self._snapshot = _HybridSnapshot(points=[], lexical_index=None)

    def ensure_collection(self) -> None:
        from qdrant_client.models import Distance, VectorParams

        if self._client.collection_exists(self.collection_name):
            return
        self._client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
        )

    def delete_building(self, building_id: str) -> None:
        from qdrant_client.models import FieldCondition, Filter, MatchValue

        points, _ = self._client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="building_id",
                        match=MatchValue(value=str(building_id)),
                    )
                ]
            ),
            limit=1000,
            with_payload=False,
            with_vectors=False,
        )
        point_ids = [point.id for point in points]
        if point_ids:
            self._client.delete(
                collection_name=self.collection_name,
                points_selector=point_ids,
            )

    def upsert(self, points: list[StoredPoint]) -> None:
        from qdrant_client.models import PointStruct

        self._client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(id=point.id, vector=point.vector, payload=point.payload)
                for point in points
            ],
        )

    def iter_points(self) -> list[StoredPoint]:
        points: list[StoredPoint] = []
        offset: int | str | None = None
        while True:
            batch, offset = self._client.scroll(
                collection_name=self.collection_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=True,
            )
            if not batch:
                break
            for point in batch:
                points.append(
                    StoredPoint(
                        id=str(point.id),
                        vector=_point_vector(point.vector),
                        payload=dict(point.payload or {}),
                    )
                )
            if offset is None:
                break
        return sorted(points, key=lambda point: point.id)

    def rebuild_lexical_index(self) -> None:
        self._snapshot = _HybridSnapshot.build(self.iter_points())

    def search(
        self,
        query_vector: list[float],
        query_text: str,
        *,
        building_id: str | None,
        limit: int,
    ) -> list[dict[str, Any]]:
        snapshot = self._snapshot
        if not snapshot.points:
            self.rebuild_lexical_index()
            snapshot = self._snapshot
        return _build_ranked_results(
            snapshot.points,
            snapshot.lexical_index,
            query_vector,
            query_text,
            building_id=building_id,
            limit=limit,
        )
