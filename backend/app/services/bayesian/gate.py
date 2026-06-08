"""Bayesian L3 data and training gates (Phase 5 L3-0)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.services.bayesian.service import count_active_accident_cases

L3_MIN_CASES = 200


def check_l3_case_gate(db: Session, *, tenant_id: str, min_cases: int = L3_MIN_CASES) -> dict:
    case_count = count_active_accident_cases(db, tenant_id=tenant_id)
    passed = case_count >= min_cases
    return {
        "tenant_id": tenant_id,
        "case_count": case_count,
        "min_cases": min_cases,
        "passed": passed,
        "message": "ok" if passed else f"requires at least {min_cases} active accident cases",
    }
