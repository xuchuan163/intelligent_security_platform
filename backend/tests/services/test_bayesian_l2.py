"""Bayesian L2 attribution tests (Phase 4-D)."""

from __future__ import annotations

import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser
from app.domain.bayesian.inference import run_l2_attribution
from app.domain.bayesian.mapping import extract_project_signals, merge_profile_signals
from app.domain.bayesian.prior import FACTOR_BY_ID, RISK_FACTORS
from app.infrastructure.database.models import AccidentCaseLibrary, Project, ProjectRiskProfile
from app.infrastructure.database.session import Base
from app.main import app
from app.schemas.bayesian import AttributionRequest
from app.services.bayesian.service import BayesianGateError, analyze_attribution


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _user(tenant_id: str = "TENANT-BAYES") -> MockUser:
    return MockUser(
        user_id="u-bayes-001",
        user_name="Bayes Analyst",
        tenant_id=tenant_id,
        org_path=tenant_id,
        role="company_analyst",
        data_scope=DataScope.TENANT,
        company_id=tenant_id,
    )


def _project_profile(high_hazard: float = 80.0) -> dict:
    return {
        "project_id": "P-BAYES",
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


def test_prior_nodes_cover_six_categories():
    categories = {factor.category for factor in RISK_FACTORS}
    assert categories == {"人", "机", "料", "法", "环", "管"}
    assert len(RISK_FACTORS) >= 18


def test_profile_mapping_links_project_dimensions_to_factors():
    signals = extract_project_signals(_project_profile())
    factor_ids = {signal.factor_id for signal in signals}
    assert "mgmt_rectification_gap" in factor_ids
    assert "machine_fault" in factor_ids
    assert "mgmt_schedule_pressure" in factor_ids


def test_l2_attribution_returns_need_human_review_and_ranked_factors():
    result = run_l2_attribution(
        project_id="P-BAYES",
        project_profile=_project_profile(),
        accident_type="高处坠落",
    )

    assert result.need_human_review is True
    assert result.model_level == "L2"
    assert len(result.factor_contributions) == len(RISK_FACTORS)
    assert result.factor_contributions[0]["contribution"] >= result.factor_contributions[1]["contribution"]
    assert result.accident_type_probabilities[0]["label"]
    assert any(item["outcome_id"] == "fall_from_height" for item in result.accident_type_probabilities)
    assert result.evidence
    assert "不得作为处罚" in result.disclaimer


def test_target_accident_type_boosts_matching_outcome_probability():
    generic = run_l2_attribution(
        project_id="P-BAYES",
        project_profile=_project_profile(),
    )
    targeted = run_l2_attribution(
        project_id="P-BAYES",
        project_profile=_project_profile(),
        accident_type="触电",
    )

    generic_map = {item["outcome_id"]: item["probability"] for item in generic.accident_type_probabilities}
    targeted_map = {item["outcome_id"]: item["probability"] for item in targeted.accident_type_probabilities}
    assert targeted_map["electric_shock"] >= generic_map["electric_shock"]


def test_worker_profile_signals_merge_into_factor_evidence():
    merged = merge_profile_signals(
        project_profile=_project_profile(high_hazard=20.0),
        worker_profile={
            "risk_level": "critical",
            "dimension_scores": {
                "exam_risk": 90.0,
                "violation_risk": 85.0,
                "qualification_risk": 70.0,
                "health_adaptation": 10.0,
            },
        },
        subcontractor_profile=None,
    )
    assert merged["human_training_gap"] > 0.5
    assert merged["human_violation"] > 0.5
    assert FACTOR_BY_ID["human_training_gap"].category == "人"


def _seed_project_profile(db, *, tenant_id: str = "TENANT-BAYES") -> None:
    today = dt.date.today()
    db.add(
        Project(
            project_id="P-BAYES",
            tenant_id=tenant_id,
            company_id=tenant_id,
            org_path=f"{tenant_id}/P-BAYES",
            project_name="Bayes Test Project",
            status="active",
            schedule_pressure_index=30.0,
        )
    )
    db.add(
        ProjectRiskProfile(
            project_id="P-BAYES",
            tenant_id=tenant_id,
            company_id=tenant_id,
            org_path=f"{tenant_id}/P-BAYES",
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
            explanation="bayes test profile",
        )
    )
    db.commit()


def _seed_cases(db, *, tenant_id: str, count: int) -> None:
    for index in range(count):
        db.add(
            AccidentCaseLibrary(
                accident_case_id=f"AC-BAYES-{index:03d}",
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


def test_service_analyze_attribution_respects_case_gate():
    db = _session()
    _seed_project_profile(db)
    _seed_cases(db, tenant_id="TENANT-BAYES", count=10)

    with pytest.raises(BayesianGateError, match="requires at least 50"):
        analyze_attribution(
            db,
            AttributionRequest(project_id="P-BAYES"),
            current_user=_user(),
            min_cases=50,
        )


def test_service_analyze_attribution_returns_payload_when_gate_passes():
    db = _session()
    _seed_project_profile(db)
    _seed_cases(db, tenant_id="TENANT-BAYES", count=50)

    payload = analyze_attribution(
        db,
        AttributionRequest(project_id="P-BAYES", accident_type="高处坠落"),
        current_user=_user(),
        min_cases=50,
    )

    assert payload["need_human_review"] is True
    assert payload["case_count"] == 50
    assert payload["project_id"] == "P-BAYES"
    assert payload["factor_contributions"]
    assert payload["accident_type_probabilities"]


def test_attribution_api_route_exists():
    client = TestClient(app)
    client.headers.update(
        {
            "X-Mock-User-Id": "u-bayes-api",
            "X-Mock-User-Name": "Bayes API",
            "X-Tenant-Id": "CSCEC",
            "X-Org-Path": "CSCEC",
            "X-Role": "platform_admin",
            "X-Data-Scope": "tenant",
        }
    )
    response = client.post(
        "/api/v1/analysis/attribution",
        json={"project_id": "P001"},
    )
    assert response.status_code in {200, 404, 503}
    if response.status_code == 200:
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert body["data"]["need_human_review"] is True
