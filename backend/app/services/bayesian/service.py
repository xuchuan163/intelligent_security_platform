"""Bayesian L2 attribution service: profile loading + inference gate (Phase 4-D)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import MockUser, assert_project_access
from app.domain.bayesian.inference import run_l2_attribution
from app.infrastructure.database.models import AccidentCaseLibrary
from app.schemas.bayesian import AttributionRequest
from app.services.profiles.service import (
    get_project_profile,
    get_subcontractor_profile,
    get_worker_profile,
)

DEFAULT_MIN_CASES = 50


class BayesianGateError(Exception):
    """Raised when L2 attribution prerequisites are not met."""


def count_active_accident_cases(db: Session, *, tenant_id: str) -> int:
    return (
        db.query(AccidentCaseLibrary)
        .filter(
            AccidentCaseLibrary.tenant_id == tenant_id,
            AccidentCaseLibrary.status == "active",
        )
        .count()
    )


def analyze_attribution(
    db: Session,
    request: AttributionRequest,
    *,
    current_user: MockUser,
    min_cases: int = DEFAULT_MIN_CASES,
) -> dict:
    assert_project_access(request.project_id, current_user)

    case_count = count_active_accident_cases(db, tenant_id=current_user.tenant_id)
    if case_count < min_cases:
        raise BayesianGateError(
            f"Bayesian L2 requires at least {min_cases} active accident cases; current={case_count}"
        )

    project_profile = get_project_profile(db, request.project_id, current_user=current_user)
    if project_profile is None:
        raise LookupError("Project profile not found")

    worker_profile = None
    if request.worker_id:
        worker_profile = get_worker_profile(db, request.worker_id, current_user=current_user)

    subcontractor_profile = None
    if request.subcontractor_id:
        subcontractor_profile = get_subcontractor_profile(
            db,
            request.subcontractor_id,
            current_user=current_user,
        )

    result = run_l2_attribution(
        project_id=request.project_id,
        project_profile=project_profile,
        worker_profile=worker_profile,
        subcontractor_profile=subcontractor_profile,
        worker_id=request.worker_id,
        subcontractor_id=request.subcontractor_id,
        accident_type=request.accident_type,
    )
    payload = result.to_dict()
    payload["case_count"] = case_count
    return payload
