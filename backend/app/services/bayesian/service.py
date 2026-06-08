"""Bayesian attribution service: L2/L3 routing and profile loading (Phase 4-D / 5 L3-D)."""

from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from app.core.security import MockUser, assert_project_access
from app.domain.bayesian.inference import run_l2_attribution
from app.domain.bayesian.l3_inference import run_l3_attribution
from app.schemas.bayesian import AttributionRequest
from app.services.bayesian.gate import L3_MIN_CASES, count_active_accident_cases
from app.domain.bayesian.cpt import cpt_learned_available
from app.services.bayesian.graph_evidence import collect_graph_supplemental_evidence
from app.services.profiles.service import (
    get_project_profile,
    get_subcontractor_profile,
    get_worker_profile,
)

DEFAULT_MIN_CASES = 50
ModelLevel = Literal["auto", "L2", "L3"]


class BayesianGateError(Exception):
    """Raised when Bayesian attribution prerequisites are not met."""


def resolve_model_level(
    requested: ModelLevel,
    *,
    case_count: int,
    cpt_available: bool,
) -> Literal["L2", "L3"]:
    if requested == "L2":
        return "L2"
    if requested == "L3":
        return "L3"
    if case_count >= L3_MIN_CASES and cpt_available:
        return "L3"
    return "L2"


def analyze_attribution(
    db: Session,
    request: AttributionRequest,
    *,
    current_user: MockUser,
    min_cases: int = DEFAULT_MIN_CASES,
) -> dict:
    assert_project_access(request.project_id, current_user)

    case_count = count_active_accident_cases(db, tenant_id=current_user.tenant_id)
    cpt_available = cpt_learned_available()
    model_level = resolve_model_level(
        request.model_level,
        case_count=case_count,
        cpt_available=cpt_available,
    )

    if model_level == "L3":
        if case_count < L3_MIN_CASES:
            raise BayesianGateError(
                f"Bayesian L3 requires at least {L3_MIN_CASES} active accident cases; current={case_count}"
            )
        if not cpt_available:
            raise BayesianGateError("Bayesian L3 learned CPT is missing; run train_bayesian_l3.py first")
        min_cases = L3_MIN_CASES
    elif case_count < min_cases:
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

    if model_level == "L3":
        graph_boosts, graph_records, neo4j_status = collect_graph_supplemental_evidence(
            project_id=request.project_id,
            worker_id=request.worker_id,
            subcontractor_id=request.subcontractor_id,
            current_user=current_user,
        )
        result = run_l3_attribution(
            project_id=request.project_id,
            project_profile=project_profile,
            worker_profile=worker_profile,
            subcontractor_profile=subcontractor_profile,
            worker_id=request.worker_id,
            subcontractor_id=request.subcontractor_id,
            accident_type=request.accident_type,
            graph_factor_boosts=graph_boosts,
            graph_supplemental_evidence=graph_records,
            neo4j_evidence_status=neo4j_status,
        )
    else:
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
    payload["requested_model_level"] = request.model_level
    payload["resolved_model_level"] = model_level
    return payload
