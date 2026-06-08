"""Build L3 training rows from accident cases (Phase 5 L3-B.4)."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.domain.bayesian.case_labels import label_accident_case_row
from app.infrastructure.database.models import AccidentCaseLibrary
from app.services.cases.backtest import build_backtest_case_from_accident_row


def accident_row_to_dict(row: AccidentCaseLibrary) -> dict[str, Any]:
    return {
        "accident_case_id": row.accident_case_id,
        "tenant_id": row.tenant_id,
        "accident_type": row.accident_type,
        "severity": row.severity,
        "project_type": row.project_type,
        "operation_scene": row.operation_scene,
        "direct_cause": row.direct_cause,
        "indirect_cause": row.indirect_cause,
        "involved_subjects": row.involved_subjects,
        "warning_indicators": row.warning_indicators if isinstance(row.warning_indicators, list) else [],
        "tags": row.tags,
        "status": row.status,
    }


def build_l3_training_row(row: AccidentCaseLibrary | dict[str, Any]) -> dict[str, Any]:
    payload = accident_row_to_dict(row) if isinstance(row, AccidentCaseLibrary) else dict(row)
    labels = label_accident_case_row(payload)
    backtest_case = None
    if isinstance(row, AccidentCaseLibrary):
        backtest_case = build_backtest_case_from_accident_row(row)
    return {
        **labels,
        "tenant_id": payload.get("tenant_id"),
        "severity": payload.get("severity"),
        "project_type": payload.get("project_type"),
        "mapped_indicator_count": backtest_case.get("mapped_indicator_count") if backtest_case else None,
    }


def load_l3_training_rows(
    db: Session,
    *,
    tenant_id: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    query = db.query(AccidentCaseLibrary).filter(AccidentCaseLibrary.status == "active")
    if tenant_id:
        query = query.filter(AccidentCaseLibrary.tenant_id == tenant_id)
    query = query.order_by(AccidentCaseLibrary.accident_case_id.asc())
    if limit is not None:
        query = query.limit(limit)
    return [build_l3_training_row(row) for row in query.all()]
