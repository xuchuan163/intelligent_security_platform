from __future__ import annotations

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session

from app.infrastructure.database.models import AccidentCaseLibrary
from app.services.cases.service import accident_case_to_item


def _keyword_pattern(query: str) -> str:
    normalized = " ".join(query.strip().split())
    return f"%{normalized}%"


def _rank_key(query: str, row: AccidentCaseLibrary) -> tuple[int, int, str]:
    normalized = " ".join(query.strip().split())
    if not normalized:
        return (9, 0, row.accident_case_id)

    if row.accident_type == normalized:
        return (0, 0, row.accident_case_id)

    score = 0
    if normalized in (row.accident_type or ""):
        score += 80

    for field in (
        row.operation_scene,
        row.direct_cause,
        row.indirect_cause,
        row.rectification_measures,
    ):
        text = field or ""
        if normalized in text:
            score += 60
        elif any(token and token in text for token in normalized.split()):
            score += 20

    tags_text = str(row.tags or "")
    if normalized in tags_text:
        score += 40
    elif any(token and token in tags_text for token in normalized.split()):
        score += 15

    return (1, -score, row.accident_case_id)


def keyword_search_accident_cases(
    db: Session,
    *,
    tenant_id: str,
    query: str,
    limit: int = 10,
    status: str = "active",
) -> list[dict]:
    pattern = _keyword_pattern(query)
    if pattern == "%%":
        return []

    text_filters = or_(
        AccidentCaseLibrary.accident_type.like(pattern),
        AccidentCaseLibrary.operation_scene.like(pattern),
        AccidentCaseLibrary.direct_cause.like(pattern),
        AccidentCaseLibrary.indirect_cause.like(pattern),
        AccidentCaseLibrary.rectification_measures.like(pattern),
        cast(AccidentCaseLibrary.tags, String).like(pattern),
    )

    rows = (
        db.query(AccidentCaseLibrary)
        .filter(
            AccidentCaseLibrary.tenant_id == tenant_id,
            AccidentCaseLibrary.status == status,
            text_filters,
        )
        .all()
    )
    ranked = sorted(rows, key=lambda row: _rank_key(query, row))
    return [accident_case_to_item(row) for row in ranked[:limit]]
