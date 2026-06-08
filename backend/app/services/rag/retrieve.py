from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.milvus_client import MilvusClient, build_milvus_client_optional
from app.services.rag.collections import (
    ACCIDENT_CASES_COLLECTION,
    ACCIDENT_CASES_PRIMARY_FIELD,
    SAFETY_KNOWLEDGE_COLLECTION,
    SAFETY_KNOWLEDGE_PRIMARY_FIELD,
)
from app.services.rag.embedding import EmbeddingProvider, build_embedding_provider
from app.services.rag.keyword_search import keyword_search_accident_cases

RetrieveMode = Literal["milvus", "mysql_keyword"]

ACCIDENT_CASES_OUTPUT_FIELDS = [
    ACCIDENT_CASES_PRIMARY_FIELD,
    "tenant_id",
    "title",
    "summary",
    "tags",
]
SAFETY_KNOWLEDGE_OUTPUT_FIELDS = [
    SAFETY_KNOWLEDGE_PRIMARY_FIELD,
    "tenant_id",
    "source_doc",
    "title",
    "content",
    "tags",
]


@dataclass(frozen=True)
class RagHit:
    collection: str
    record_id: str
    tenant_id: str
    title: str
    content: str
    score: float
    tags: str | None = None
    source_doc: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "collection": self.collection,
            "record_id": self.record_id,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "content": self.content,
            "score": round(self.score, 4),
        }
        if self.tags is not None:
            payload["tags"] = self.tags
        if self.source_doc is not None:
            payload["source_doc"] = self.source_doc
        return payload


def build_tenant_filter(tenant_id: str) -> str:
    escaped = tenant_id.replace("\\", "\\\\").replace('"', '\\"')
    return f'tenant_id == "{escaped}"'


def distance_to_score(distance: float) -> float:
    # Milvus COSINE distance: 0 means identical vectors.
    return max(0.0, min(1.0, 1.0 - float(distance)))


def _parse_search_hits(
    raw_hits: list[dict[str, Any]],
    *,
    collection: str,
    id_field: str,
    content_field: str,
    score_threshold: float,
) -> list[RagHit]:
    parsed: list[RagHit] = []
    for hit in raw_hits:
        score = distance_to_score(hit.get("distance", 1.0))
        if score < score_threshold:
            continue
        entity = hit.get("entity") or {}
        parsed.append(
            RagHit(
                collection=collection,
                record_id=str(entity.get(id_field, hit.get("id", ""))),
                tenant_id=str(entity.get("tenant_id", "")),
                title=str(entity.get("title", "")),
                content=str(entity.get(content_field, "")),
                score=score,
                tags=entity.get("tags"),
                source_doc=entity.get("source_doc"),
            )
        )
    return parsed


def vector_search_collection(
    client: MilvusClient,
    *,
    collection_name: str,
    query_vector: list[float],
    tenant_id: str,
    top_k: int,
    score_threshold: float,
    output_fields: list[str],
    id_field: str,
    content_field: str,
) -> list[RagHit]:
    if not client.has_collection(collection_name):
        return []

    raw = client.search(
        collection_name=collection_name,
        data=[query_vector],
        filter_expr=build_tenant_filter(tenant_id),
        limit=top_k,
        output_fields=output_fields,
    )
    batch = raw[0] if raw else []
    return _parse_search_hits(
        batch,
        collection=collection_name,
        id_field=id_field,
        content_field=content_field,
        score_threshold=score_threshold,
    )


def retrieve_rag_hits(
    client: MilvusClient,
    *,
    query: str,
    tenant_id: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
    collections: list[str] | None = None,
    embedder: EmbeddingProvider | None = None,
) -> list[RagHit]:
    top_k = top_k or settings.rag_top_k
    score_threshold = score_threshold if score_threshold is not None else settings.rag_score_threshold
    embedder = embedder or build_embedding_provider()
    target_collections = collections or [
        settings.milvus_accident_cases_collection,
        settings.milvus_safety_knowledge_collection,
    ]

    vectors = embedder.embed_texts([query])
    if not vectors:
        return []
    query_vector = vectors[0]

    hits: list[RagHit] = []
    for collection_name in target_collections:
        if collection_name == settings.milvus_accident_cases_collection:
            hits.extend(
                vector_search_collection(
                    client,
                    collection_name=collection_name,
                    query_vector=query_vector,
                    tenant_id=tenant_id,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    output_fields=ACCIDENT_CASES_OUTPUT_FIELDS,
                    id_field=ACCIDENT_CASES_PRIMARY_FIELD,
                    content_field="summary",
                )
            )
        elif collection_name == settings.milvus_safety_knowledge_collection:
            hits.extend(
                vector_search_collection(
                    client,
                    collection_name=collection_name,
                    query_vector=query_vector,
                    tenant_id=tenant_id,
                    top_k=top_k,
                    score_threshold=score_threshold,
                    output_fields=SAFETY_KNOWLEDGE_OUTPUT_FIELDS,
                    id_field=SAFETY_KNOWLEDGE_PRIMARY_FIELD,
                    content_field="content",
                )
            )

    hits.sort(key=lambda item: item.score, reverse=True)
    return hits[:top_k]


def _keyword_fallback_hits(
    db: Session,
    *,
    query: str,
    tenant_id: str,
    limit: int,
) -> list[RagHit]:
    rows = keyword_search_accident_cases(db, tenant_id=tenant_id, query=query, limit=limit)
    return [
        RagHit(
            collection=ACCIDENT_CASES_COLLECTION,
            record_id=row["accident_case_id"],
            tenant_id=row["tenant_id"],
            title=row.get("accident_type") or row["accident_case_id"],
            content="\n".join(
                part
                for part in [
                    row.get("direct_cause") or "",
                    row.get("indirect_cause") or "",
                    row.get("rectification_measures") or "",
                ]
                if part
            ),
            score=0.5,
            tags=str(row.get("tags")),
        )
        for row in rows
    ]


def retrieve_with_fallback(
    db: Session,
    *,
    query: str,
    tenant_id: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
    milvus_client: MilvusClient | None = None,
    embedder: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    top_k = top_k or settings.rag_top_k
    owns_client = milvus_client is None
    client = milvus_client if milvus_client is not None else build_milvus_client_optional()

    try:
        if client is not None and client.ping():
            hits = retrieve_rag_hits(
                client,
                query=query,
                tenant_id=tenant_id,
                top_k=top_k,
                score_threshold=score_threshold,
                embedder=embedder,
            )
            if hits:
                return {
                    "mode": "milvus",
                    "query": query,
                    "tenant_id": tenant_id,
                    "top_k": top_k,
                    "score_threshold": score_threshold or settings.rag_score_threshold,
                    "total": len(hits),
                    "items": [hit.as_dict() for hit in hits],
                }

        fallback_hits = _keyword_fallback_hits(db, query=query, tenant_id=tenant_id, limit=top_k)
        return {
            "mode": "mysql_keyword",
            "query": query,
            "tenant_id": tenant_id,
            "top_k": top_k,
            "score_threshold": score_threshold or settings.rag_score_threshold,
            "total": len(fallback_hits),
            "items": [hit.as_dict() for hit in fallback_hits],
        }
    finally:
        if owns_client and client is not None:
            client.close()
