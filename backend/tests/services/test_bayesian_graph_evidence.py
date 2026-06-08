"""Neo4j supplemental evidence for Bayesian L3 (Phase 5 L3-D.5)."""

from __future__ import annotations

import pytest

from app.core.security import DataScope, MockUser, ScopeType
from app.domain.bayesian.cpt import cpt_learned_available, load_cpt_learned
from app.domain.bayesian.l3_inference import run_l3_attribution
from app.services.bayesian.graph_evidence import (
    GRAPH_FACTOR_BOOST_CAP,
    build_graph_supplemental_evidence,
    collect_graph_supplemental_evidence,
)
from tests.services.test_graph_neighbors_tool import FakeNeo4jClient


def _user() -> MockUser:
    return MockUser(
        user_id="U-L3-GRAPH",
        user_name="L3 Graph",
        tenant_id="CSCEC",
        org_path="CSCEC",
        role="platform_admin",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def _project_profile() -> dict:
    return {
        "project_id": "P001",
        "risk_level": "high",
        "dimension_scores": {
            "hazard_rectification": 70.0,
            "equipment_mechanical": 40.0,
            "schedule_pressure": 30.0,
            "subcontractor_transfer": 20.0,
            "behavior_risk": 25.0,
        },
    }


def test_graph_supplemental_evidence_disabled_without_client():
    boosts, records, status = collect_graph_supplemental_evidence(
        project_id="P001",
        worker_id=None,
        subcontractor_id=None,
        current_user=_user(),
        client=None,
    )
    assert status in {"disabled", "unavailable"}
    assert boosts == {}
    assert records == []


def test_build_graph_supplemental_evidence_caps_boost_strength():
    neighbors = [
        {
            "relationship": "HAS_HAZARD",
            "node_type": "hazard",
            "anchor_type": "project",
            "anchor_id": "P001",
            "properties": {"hazard_id": "H001", "hazard_type": "scaffold"},
        }
    ]
    boosts, records = build_graph_supplemental_evidence(neighbors)
    assert records
    assert records[0]["source"] == "graph"
    assert records[0]["weight_tier"] == "supplemental"
    assert all(value <= GRAPH_FACTOR_BOOST_CAP for value in boosts.values())


def test_collect_graph_supplemental_evidence_with_fake_neo4j_client():
    client = FakeNeo4jClient(
        rows=[
            {
                "relationship": "HAS_HAZARD",
                "labels": ["Hazard"],
                "properties": {
                    "hazard_id": "H002",
                    "tenant_id": "CSCEC",
                    "org_path": "CSCEC/P001",
                    "hazard_type": "scaffold",
                },
            }
        ]
    )
    boosts, records, status = collect_graph_supplemental_evidence(
        project_id="P001",
        worker_id=None,
        subcontractor_id=None,
        current_user=_user(),
        client=client,
    )
    assert status == "applied"
    assert "mgmt_rectification_gap" in boosts or "machine_guard_failure" in boosts
    assert records


@pytest.mark.skipif(not cpt_learned_available(), reason="cpt_learned.json missing")
def test_l3_attribution_includes_graph_supplemental_evidence():
    graph_records = [
        {
            "factor_id": "mgmt_rectification_gap",
            "source": "graph",
            "field": "neo4j.HAS_HAZARD.hazard",
            "value": "H002",
            "strength": 0.12,
            "weight_tier": "supplemental",
        }
    ]
    baseline = run_l3_attribution(
        project_id="P001",
        project_profile=_project_profile(),
        accident_type="高处坠落",
        cpt_payload=load_cpt_learned(),
        neo4j_evidence_status="disabled",
    )
    enriched = run_l3_attribution(
        project_id="P001",
        project_profile=_project_profile(),
        accident_type="高处坠落",
        cpt_payload=load_cpt_learned(),
        graph_factor_boosts={"mgmt_rectification_gap": 0.12},
        graph_supplemental_evidence=graph_records,
        neo4j_evidence_status="applied",
    )
    assert enriched.neo4j_evidence_status == "applied"
    assert enriched.graph_supplemental_evidence
    assert any(item.get("source") == "graph" for item in enriched.to_dict()["evidence"])
    assert enriched.factor_contributions != baseline.factor_contributions or enriched.evidence != baseline.evidence
