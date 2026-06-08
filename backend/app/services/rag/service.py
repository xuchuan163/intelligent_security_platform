from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.services.rag.retrieve import retrieve_with_fallback


def search_rag(
    db: Session,
    *,
    tenant_id: str,
    query: str,
    top_k: int | None = None,
    score_threshold: float | None = None,
) -> dict[str, Any]:
    return retrieve_with_fallback(
        db,
        query=query,
        tenant_id=tenant_id,
        top_k=top_k,
        score_threshold=score_threshold,
    )
