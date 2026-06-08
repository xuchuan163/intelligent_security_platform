from __future__ import annotations

import hashlib
import struct
from typing import Protocol

import httpx

from app.core.config import settings


class EmbeddingProvider(Protocol):
    provider: str

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...


def _normalize_texts(texts: list[str]) -> list[str]:
    return [" ".join(text.strip().split()) for text in texts if text and text.strip()]


def _mock_vector(text: str, *, dimension: int) -> list[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    while len(values) < dimension:
        for offset in range(0, len(digest), 4):
            if len(values) >= dimension:
                break
            chunk = digest[offset : offset + 4].ljust(4, b"\0")
            values.append((struct.unpack(">I", chunk)[0] / 2**32) * 2 - 1)
        digest = hashlib.sha256(digest).digest()
    return values[:dimension]


class MockEmbeddingProvider:
    provider = "mock"

    def __init__(self, *, dimension: int | None = None) -> None:
        self.dimension = dimension or settings.milvus_embedding_dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        normalized = _normalize_texts(texts)
        return [_mock_vector(text, dimension=self.dimension) for text in normalized]


class DashScopeEmbeddingProvider:
    provider = "dashscope"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        dimension: int | None = None,
        batch_size: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.dashscope_api_key
        self.model = model or settings.embedding_model
        self.dimension = dimension or settings.milvus_embedding_dimension
        self.batch_size = batch_size or settings.embedding_batch_size
        if not self.api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required for dashscope embedding provider")

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        normalized = _normalize_texts(texts)
        if not normalized:
            return []

        vectors: list[list[float]] = []
        for start in range(0, len(normalized), self.batch_size):
            batch = normalized[start : start + self.batch_size]
            vectors.extend(self._embed_batch(batch))
        return vectors

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        with httpx.Client(timeout=30) as client:
            response = client.post(
                "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": {"texts": texts},
                    "parameters": {"dimension": self.dimension},
                },
            )
        if response.status_code != 200:
            raise RuntimeError(f"DashScope embedding failed: HTTP {response.status_code}")

        payload = response.json()
        embeddings = payload.get("output", {}).get("embeddings", [])
        if len(embeddings) != len(texts):
            raise RuntimeError("DashScope embedding response size mismatch")
        return [item["embedding"] for item in embeddings]


def build_embedding_provider() -> EmbeddingProvider:
    provider = settings.embedding_provider.strip().lower()
    if provider in {"disabled", "mock"}:
        return MockEmbeddingProvider()
    if provider == "dashscope":
        return DashScopeEmbeddingProvider()
    raise RuntimeError(f"Unsupported embedding provider: {settings.embedding_provider}")
