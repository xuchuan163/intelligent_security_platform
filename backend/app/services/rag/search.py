from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.milvus_client import MilvusClient
from app.services.rag.retrieve import retrieve_with_fallback


def search_accident_cases_with_fallback(
    db: Session,
    *,
    tenant_id: str,
    query: str,
    limit: int = 10,
    milvus_client: MilvusClient | None = None,
    score_threshold: float | None = None,
) -> dict[str, Any]:
    return retrieve_with_fallback(
        db,
        query=query,
        tenant_id=tenant_id,
        top_k=limit,
        score_threshold=score_threshold,
        milvus_client=milvus_client,
    )
