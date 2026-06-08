"""Bayesian L3 CPT cold-start tests (Phase 5 L3-A.3/A.4)."""

from __future__ import annotations

from app.domain.bayesian.cpt import (
    FACTOR_STATES,
    OUTCOME_STATES,
    build_cpt_prior_payload,
    load_cpt_prior,
    write_cpt_prior_file,
)
from app.domain.bayesian.prior import ACCIDENT_OUTCOMES, RISK_FACTORS
from app.domain.bayesian.structure import load_network_structure


def test_build_cpt_prior_payload_matches_structure_nodes():
    structure = load_network_structure()
    payload = build_cpt_prior_payload(structure)
    assert payload["model_level"] == "L3"
    assert payload["factor_count"] == len(RISK_FACTORS)
    assert payload["outcome_count"] == len(ACCIDENT_OUTCOMES)
    assert set(payload["nodes"]) == structure.node_ids


def test_factor_cpt_states_and_probabilities_sum_to_one():
    payload = build_cpt_prior_payload()
    for node_id, node in payload["nodes"].items():
        if node["kind"] != "factor":
            continue
        assert node["states"] == list(FACTOR_STATES)
        total = sum(node["probabilities"].values())
        assert abs(total - 1.0) < 0.001


def test_outcome_cpt_states_present():
    payload = build_cpt_prior_payload()
    outcome_nodes = [node for node in payload["nodes"].values() if node["kind"] == "outcome"]
    assert outcome_nodes
    for node in outcome_nodes:
        assert node["states"] == list(OUTCOME_STATES)
        total = sum(node["probabilities"].values())
        assert abs(total - 1.0) < 0.001


def test_write_and_load_cpt_prior_file(tmp_path):
    target = tmp_path / "cpt_prior.json"
    written = write_cpt_prior_file(target)
    loaded = load_cpt_prior(written)
    assert loaded["model_version"] == "bayesian-l3-prior-v1"
    assert "nodes" in loaded
