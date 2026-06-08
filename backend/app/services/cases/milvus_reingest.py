"""Optional Milvus re-ingest hook after accident case changes (Phase 4-B.6)."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.milvus_client import MilvusClient, build_milvus_client_optional
from app.services.rag.collections import ensure_accident_cases_collection
from app.services.rag.embedding import EmbeddingProvider, build_embedding_provider
from app.services.rag.ingest import ingest_accident_cases

ReingestStatus = Literal["ingested", "skipped"]


def _embedding_version_tag(*, provider: str) -> str:
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"rag-{provider}-{stamp}"


def _mark_embedding_versions(
    db: Session,
    *,
    tenant_id: str,
    version: str,
    accident_case_ids: list[str] | None = None,
) -> int:
    query = db.query(AccidentCaseLibrary).filter(
        AccidentCaseLibrary.tenant_id == tenant_id,
        AccidentCaseLibrary.status == "active",
    )
    if accident_case_ids:
        query = query.filter(AccidentCaseLibrary.accident_case_id.in_(accident_case_ids))
    rows = query.all()
    for row in rows:
        row.embedding_version = version
    if rows:
        db.commit()
    return len(rows)


def trigger_accident_case_milvus_reingest(
    db: Session,
    *,
    tenant_id: str,
    accident_case_ids: list[str] | None = None,
    milvus_client: MilvusClient | None = None,
    embedder: EmbeddingProvider | None = None,
    ensure_collection: bool = True,
) -> dict[str, Any]:
    """Re-ingest accident cases into Milvus for a tenant.

    When Milvus is disabled or unreachable, returns ``status=skipped`` without raising.
    """
    if not settings.milvus_enabled:
        return {
            "status": "skipped",
            "reason": "milvus_disabled",
            "tenant_id": tenant_id,
            "upserted": 0,
            "embedding_version_updated": 0,
        }

    owns_client = milvus_client is None
    client = milvus_client or build_milvus_client_optional()
    if client is None:
        return {
            "status": "skipped",
            "reason": "milvus_unavailable",
            "tenant_id": tenant_id,
            "upserted": 0,
            "embedding_version_updated": 0,
        }

    try:
        collection_info = None
        if ensure_collection:
            collection_info = ensure_accident_cases_collection(client).as_dict()

        embedder = embedder or build_embedding_provider()
        ingest_result = ingest_accident_cases(
            db,
            client,
            tenant_id=tenant_id,
            embedder=embedder,
        )

        version = _embedding_version_tag(provider=embedder.provider)
        updated = _mark_embedding_versions(
            db,
            tenant_id=tenant_id,
            version=version,
            accident_case_ids=accident_case_ids,
        )

        payload: dict[str, Any] = {
            "status": "ingested",
            "reason": None,
            "tenant_id": tenant_id,
            "upserted": ingest_result.upserted,
            "collection": ingest_result.collection,
            "embedding_provider": embedder.provider,
            "embedding_version": version,
            "embedding_version_updated": updated,
            "accident_case_ids": accident_case_ids or [],
        }
        if collection_info is not None:
            payload["collection_info"] = collection_info
        return payload
    finally:
        if owns_client:
            client.close()
