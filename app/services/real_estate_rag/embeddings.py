from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache
from typing import Protocol

from app.core.config import get_settings


class EmbeddingProvider(Protocol):
    model_name: str
    vector_size: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]: ...


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _normalize(text: str) -> str:
    return text.lower()


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(_normalize(text))


def _hash_token(token: str, vector_size: int) -> int:
    digest = hashlib.sha256(token.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % vector_size


class HashEmbeddingProvider:
    """Deterministic fallback embedder used when OpenAI is unavailable."""

    def __init__(self, *, vector_size: int, model_name: str = "hash-embeddings") -> None:
        self.vector_size = vector_size
        self.model_name = model_name

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            vector = [0.0] * self.vector_size
            for token in _tokens(text):
                vector[_hash_token(token, self.vector_size)] += 1.0
            norm = math.sqrt(sum(value * value for value in vector))
            if norm:
                vector = [value / norm for value in vector]
            vectors.append(vector)
        return vectors


class OpenAIEmbeddingProvider:
    def __init__(self, *, api_key: str, model_name: str, vector_size: int) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key)
        self.model_name = model_name
        self.vector_size = vector_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for index in range(0, len(texts), 100):
            batch = texts[index : index + 100]
            response = self._client.embeddings.create(
                model=self.model_name,
                input=batch,
            )
            vectors.extend([item.embedding for item in response.data])
        return vectors


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    settings = get_settings()
    if settings.OPENAI_API_KEY:
        try:
            return OpenAIEmbeddingProvider(
                api_key=settings.OPENAI_API_KEY,
                model_name=settings.QDRANT_EMBEDDING_MODEL,
                vector_size=settings.QDRANT_VECTOR_SIZE,
            )
        except Exception:
            pass
    return HashEmbeddingProvider(
        vector_size=settings.QDRANT_VECTOR_SIZE,
        model_name="hash-fallback",
    )
