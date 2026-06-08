"""Bayesian L3 inference, routing, and API tests (Phase 5 L3-D/E/F)."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser
from app.domain.bayesian.case_labels import label_accident_case_row
from app.domain.bayesian.l3_inference import run_l3_attribution
from app.infrastructure.database.models import AccidentCaseLibrary, Project, ProjectRiskProfile
from app.infrastructure.database.session import Base
from app.main import app
from app.schemas.bayesian import AttributionRequest
from app.services.bayesian.gate import L3_MIN_CASES
from app.services.bayesian.service import BayesianGateError, analyze_attribution, resolve_model_level
from app.domain.bayesian.cpt import cpt_learned_available, load_cpt_learned
from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _user(tenant_id: str = "TENANT-L3") -> MockUser:
    return MockUser(
        user_id="u-l3-001",
        user_name="L3 Analyst",
        tenant_id=tenant_id,
        org_path=tenant_id,
        role="platform_admin",
        data_scope=DataScope.TENANT,
        company_id=tenant_id,
    )


def _project_profile(high_hazard: float = 80.0) -> dict:
    return {
        "project_id": "P-L3",
        "risk_level": "high",
        "total_risk_score": 72.0,
        "dimension_scores": {
            "hazard_rectification": high_hazard,
            "equipment_mechanical": 55.0,
            "schedule_pressure": 60.0,
            "subcontractor_transfer": 40.0,
            "behavior_risk": 35.0,
        },
    }


def _seed_project_profile(db, *, tenant_id: str = "TENANT-L3") -> None:
    today = dt.date.today()
    db.add(
        Project(
            project_id="P-L3",
            tenant_id=tenant_id,
            company_id=tenant_id,
            org_path=f"{tenant_id}/P-L3",
            project_name="L3 Test Project",
            status="active",
            schedule_pressure_index=30.0,
        )
    )
    db.add(
        ProjectRiskProfile(
            project_id="P-L3",
            tenant_id=tenant_id,
            company_id=tenant_id,
            org_path=f"{tenant_id}/P-L3",
            calc_date=today,
            total_risk_score=78.0,
            risk_level="high",
            hazard_rectification_score=82.0,
            equipment_mechanical_score=60.0,
            schedule_pressure_score=55.0,
            subcontractor_transfer_score=48.0,
            behavior_risk_score=40.0,
            data_completeness=0.9,
            confidence_level="medium_high",
            explanation="l3 test profile",
        )
    )
    db.commit()


def _seed_cases(db, *, tenant_id: str, count: int) -> None:
    for index in range(count):
        db.add(
            AccidentCaseLibrary(
                accident_case_id=f"AC-L3-{index:03d}",
                tenant_id=tenant_id,
                company_id=tenant_id,
                accident_type="高处坠落",
                severity="major",
                project_type="housing",
                status="active",
                tags=["临边防护"],
            )
        )
    db.commit()


@pytest.mark.skipif(not cpt_learned_available(), reason="cpt_learned.json missing")
def test_run_l3_attribution_returns_extended_fields():
    result = run_l3_attribution(
        project_id="P-L3",
        project_profile=_project_profile(),
        accident_type="高处坠落",
        cpt_payload=load_cpt_learned(),
    )
    payload = result.to_dict()

    assert result.model_level == "L3"
    assert result.need_human_review is True
    assert payload["propagation_paths"]
    assert payload["cpt_version"]
    assert payload["structure_version"]
    assert payload["calibration_hint"]
    assert len(result.factor_contributions) == 21
    assert "传播路径" in result.disclaimer or "CPT" in result.disclaimer


@pytest.mark.skipif(not cpt_learned_available(), reason="cpt_learned.json missing")
def test_l3_top_factors_overlap_case_labels_for_golden_seed():
    cpt_payload = load_cpt_learned()
    overlaps = 0
    for seed in ACCIDENT_CASE_SEEDS[:10]:
        labels = label_accident_case_row(seed)
        labeled = {factor_id for factor_id, value in labels["factor_labels"].items() if int(value) == 1}
        if not labeled:
            continue
        result = run_l3_attribution(
            project_id="P-L3",
            project_profile=_project_profile(high_hazard=85.0),
            accident_type=seed["accident_type"],
            cpt_payload=cpt_payload,
        )
        top_factors = {row["factor_id"] for row in result.factor_contributions[:3]}
        if labeled & top_factors:
            overlaps += 1
    assert overlaps >= 5


def test_resolve_model_level_auto_fallback_to_l2():
    assert resolve_model_level("auto", case_count=50, cpt_available=True) == "L2"
    assert resolve_model_level("auto", case_count=L3_MIN_CASES, cpt_available=False) == "L2"


@pytest.mark.skipif(not cpt_learned_available(), reason="cpt_learned.json missing")
def test_resolve_model_level_auto_selects_l3():
    assert resolve_model_level("auto", case_count=L3_MIN_CASES, cpt_available=True) == "L3"


def test_service_fallback_to_l2_when_forced():
    db = _session()
    _seed_project_profile(db)
    _seed_cases(db, tenant_id="TENANT-L3", count=L3_MIN_CASES)

    payload = analyze_attribution(
        db,
        AttributionRequest(project_id="P-L3", accident_type="高处坠落", model_level="L2"),
        current_user=_user(),
        min_cases=50,
    )
    assert payload["resolved_model_level"] == "L2"
    assert payload["model_level"] == "L2"
    assert "propagation_paths" not in payload


@pytest.mark.skipif(not cpt_learned_available(), reason="cpt_learned.json missing")
def test_service_auto_routes_to_l3_with_gate_and_cpt():
    db = _session()
    _seed_project_profile(db)
    _seed_cases(db, tenant_id="TENANT-L3", count=L3_MIN_CASES)

    payload = analyze_attribution(
        db,
        AttributionRequest(project_id="P-L3", accident_type="高处坠落", model_level="auto"),
        current_user=_user(),
    )
    assert payload["resolved_model_level"] == "L3"
    assert payload["model_level"] == "L3"
    assert payload["propagation_paths"]
    assert payload["cpt_version"]


def test_service_force_l3_fails_without_enough_cases():
    db = _session()
    _seed_project_profile(db)
    _seed_cases(db, tenant_id="TENANT-L3", count=50)

    with pytest.raises(BayesianGateError, match="L3 requires at least"):
        analyze_attribution(
            db,
            AttributionRequest(project_id="P-L3", model_level="L3"),
            current_user=_user(),
        )


def test_attribution_api_accepts_model_level():
    client = TestClient(app)
    client.headers.update(
        {
            "X-Mock-User-Id": "u-l3-api",
            "X-Mock-User-Name": "L3 API",
            "X-Tenant-Id": "CSCEC",
            "X-Org-Path": "CSCEC",
            "X-Role": "platform_admin",
            "X-Data-Scope": "tenant",
        }
    )
    response = client.post(
        "/api/v1/analysis/attribution",
        json={"project_id": "P001", "model_level": "L2"},
    )
    assert response.status_code in {200, 404, 503}


@pytest.mark.skipif(not cpt_learned_available(), reason="cpt_learned.json missing")
def test_bayesian_versions_api_lists_learned_cpt():
    client = TestClient(app)
    client.headers.update(
        {
            "X-Mock-User-Id": "u-l3-config",
            "X-Tenant-Id": "CSCEC",
            "X-Org-Path": "CSCEC",
            "X-Role": "platform_admin",
            "X-Data-Scope": "tenant",
        }
    )
    response = client.get("/api/v1/config/bayesian-versions")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "SUCCESS"
    keys = {item["config_key"] for item in body["data"]["items"]}
    assert "bayesian_cpt_learned" in keys
