"""Shared outcome probability helpers for L3 inference and calibration."""

from __future__ import annotations

from typing import Any

from app.domain.bayesian.prior import ACCIDENT_OUTCOMES
from app.domain.bayesian.structure import BayesianNetworkStructure


def outcome_likelihood_for_labels(
    factor_labels: dict[str, int],
    *,
    outcome_id: str,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure,
) -> float:
    node = cpt_payload["nodes"][outcome_id]
    parents = structure.parents_of(outcome_id)
    if parents:
        active_count = sum(1 for parent_id in parents if int(factor_labels.get(parent_id, 0)) == 1)
        bucket_key = f"active_parent_count:{active_count}"
        conditional = node.get("conditional_probabilities", {})
        if bucket_key in conditional:
            return float(conditional[bucket_key]["likely"])
    return float(node["probabilities"]["likely"])


def predict_outcome_distribution(
    factor_labels: dict[str, int],
    *,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure,
) -> dict[str, float]:
    scores = {
        outcome.outcome_id: outcome_likelihood_for_labels(
            factor_labels,
            outcome_id=outcome.outcome_id,
            cpt_payload=cpt_payload,
            structure=structure,
        )
        for outcome in ACCIDENT_OUTCOMES
    }
    total = sum(scores.values()) or 1.0
    return {outcome_id: round(score / total, 6) for outcome_id, score in scores.items()}
