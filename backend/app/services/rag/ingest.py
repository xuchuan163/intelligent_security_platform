from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.milvus_client import MilvusClient
from app.services.rag.chunking import KnowledgeChunkDraft, load_knowledge_chunks
from app.services.rag.collections import (
    ACCIDENT_CASES_COLLECTION,
    SAFETY_KNOWLEDGE_COLLECTION,
    ensure_rag_collections,
)
from app.services.rag.embedding import EmbeddingProvider, build_embedding_provider


@dataclass(frozen=True)
class IngestResult:
    collection: str
    upserted: int
    skipped: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "collection": self.collection,
            "upserted": self.upserted,
            "skipped": self.skipped,
        }


def _serialize_tags(tags: Any) -> str:
    if tags is None:
        return "[]"
    if isinstance(tags, str):
        return tags
    return json.dumps(tags, ensure_ascii=False)


def _accident_case_title(row: AccidentCaseLibrary) -> str:
    return row.accident_type or row.accident_case_id


def _accident_case_summary(row: AccidentCaseLibrary) -> str:
    parts = [
        row.direct_cause or "",
        row.indirect_cause or "",
        row.rectification_measures or "",
    ]
    return "\n".join(part.strip() for part in parts if part and part.strip())


def _accident_case_embed_text(row: AccidentCaseLibrary) -> str:
    return "\n".join(
        [
            _accident_case_title(row),
            row.operation_scene or "",
            _accident_case_summary(row),
            _serialize_tags(row.tags),
        ]
    ).strip()


def build_accident_case_records(
    rows: list[AccidentCaseLibrary],
    *,
    embedder: EmbeddingProvider,
) -> list[dict[str, Any]]:
    if not rows:
        return []

    vectors = embedder.embed_texts([_accident_case_embed_text(row) for row in rows])
    if len(vectors) != len(rows):
        raise RuntimeError("Embedding count mismatch for accident cases")

    records: list[dict[str, Any]] = []
    for row, vector in zip(rows, vectors, strict=True):
        records.append(
            {
                "case_id": row.accident_case_id,
                "tenant_id": row.tenant_id,
                "title": _accident_case_title(row)[:256],
                "summary": _accident_case_summary(row)[:4096],
                "tags": _serialize_tags(row.tags)[:1024],
                "embedding": vector,
            }
        )
    return records


def build_safety_knowledge_records(
    chunks: list[KnowledgeChunkDraft],
    *,
    embedder: EmbeddingProvider,
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    vectors = embedder.embed_texts(
        [f"{chunk.title}\n{chunk.content}" for chunk in chunks]
    )
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding count mismatch for safety knowledge")

    records: list[dict[str, Any]] = []
    for chunk, vector in zip(chunks, vectors, strict=True):
        records.append(
            {
                "chunk_id": chunk.chunk_id,
                "tenant_id": chunk.tenant_id,
                "source_doc": chunk.source_doc[:128],
                "title": chunk.title[:256],
                "content": chunk.content[:4096],
                "tags": _serialize_tags(chunk.tags)[:1024],
                "embedding": vector,
            }
        )
    return records


def upsert_records(
    client: MilvusClient,
    *,
    collection_name: str,
    records: list[dict[str, Any]],
) -> IngestResult:
    if not records:
        return IngestResult(collection=collection_name, upserted=0, skipped=0)

    client.upsert(collection_name=collection_name, data=records)
    return IngestResult(collection=collection_name, upserted=len(records), skipped=0)


def ingest_accident_cases(
    db: Session,
    client: MilvusClient,
    *,
    tenant_id: str,
    embedder: EmbeddingProvider | None = None,
) -> IngestResult:
    embedder = embedder or build_embedding_provider()
    rows = (
        db.query(AccidentCaseLibrary)
        .filter(
            AccidentCaseLibrary.tenant_id == tenant_id,
            AccidentCaseLibrary.status == "active",
        )
        .order_by(AccidentCaseLibrary.accident_case_id.asc())
        .all()
    )
    records = build_accident_case_records(rows, embedder=embedder)
    return upsert_records(
        client,
        collection_name=settings.milvus_accident_cases_collection or ACCIDENT_CASES_COLLECTION,
        records=records,
    )


def ingest_safety_knowledge(
    client: MilvusClient,
    knowledge_dir: Path,
    *,
    tenant_id: str,
    embedder: EmbeddingProvider | None = None,
) -> IngestResult:
    embedder = embedder or build_embedding_provider()
    chunks = load_knowledge_chunks(knowledge_dir, tenant_id=tenant_id)
    records = build_safety_knowledge_records(chunks, embedder=embedder)
    return upsert_records(
        client,
        collection_name=settings.milvus_safety_knowledge_collection or SAFETY_KNOWLEDGE_COLLECTION,
        records=records,
    )


def ingest_rag_corpus(
    db: Session,
    client: MilvusClient,
    *,
    knowledge_dir: Path,
    tenant_id: str | None = None,
    embedder: EmbeddingProvider | None = None,
) -> dict[str, Any]:
    tenant = tenant_id or settings.rag_default_tenant_id
    embedder = embedder or build_embedding_provider()
    collections = ensure_rag_collections(client)
    accident_result = ingest_accident_cases(db, client, tenant_id=tenant, embedder=embedder)
    knowledge_result = ingest_safety_knowledge(
        client,
        knowledge_dir,
        tenant_id=tenant,
        embedder=embedder,
    )
    return {
        "tenant_id": tenant,
        "embedding_provider": embedder.provider,
        "collections": [item.as_dict() for item in collections],
        "ingest": [accident_result.as_dict(), knowledge_result.as_dict()],
    }
