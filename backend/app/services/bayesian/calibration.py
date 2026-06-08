"""Bayesian L3 calibration metrics on holdout cases (Phase 5 L3-C.4)."""

from __future__ import annotations

import random
from typing import Any

from app.domain.bayesian.outcome_probs import predict_outcome_distribution as _predict_from_labels
from app.domain.bayesian.prior import ACCIDENT_OUTCOMES, RISK_FACTORS
from app.domain.bayesian.structure import BayesianNetworkStructure, load_network_structure
from app.services.bayesian.training import learn_cpt_from_training_rows


def build_outcome_factor_affinity(train_rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    affinity: dict[str, dict[str, float]] = {}
    for outcome in ACCIDENT_OUTCOMES:
        cases = [row for row in train_rows if row.get("outcome_id") == outcome.outcome_id]
        if not cases:
            continue
        outcome_map: dict[str, float] = {}
        for factor in RISK_FACTORS:
            active = sum(
                1
                for row in cases
                if int(row.get("factor_labels", {}).get(factor.factor_id, 0)) == 1
            )
            outcome_map[factor.factor_id] = round(active / len(cases), 4)
        affinity[outcome.outcome_id] = outcome_map
    return affinity


def split_training_rows(
    rows: list[dict[str, Any]],
    *,
    holdout_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows:
        return [], []
    shuffled = list(rows)
    rng = random.Random(seed)
    rng.shuffle(shuffled)
    holdout_size = max(1, int(len(shuffled) * holdout_ratio))
    holdout = shuffled[:holdout_size]
    train = shuffled[holdout_size:]
    if not train:
        train = holdout
        holdout = []
    return train, holdout


def predict_outcome_distribution(
    row: dict[str, Any],
    *,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure,
) -> dict[str, float]:
    factor_labels = {
        factor_id: int(value)
        for factor_id, value in row.get("factor_labels", {}).items()
        if int(value) == 1
    }
    return _predict_from_labels(factor_labels, cpt_payload=cpt_payload, structure=structure)


def _parent_score(
    parent_id: str,
    *,
    row: dict[str, Any],
    outcome_id: str,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure,
) -> float:
    parents = structure.parents_of(outcome_id)
    factor_labels = row.get("factor_labels", {})
    active_count = sum(1 for pid in parents if int(factor_labels.get(pid, 0)) == 1)
    outcome_node = cpt_payload["nodes"][outcome_id]
    bucket_key = f"active_parent_count:{active_count}"
    conditional = outcome_node.get("conditional_probabilities", {}).get(
        bucket_key,
        outcome_node["probabilities"],
    )
    parent_active = float(cpt_payload["nodes"][parent_id]["probabilities"]["active"])
    return parent_active * float(conditional["likely"])


def factor_hit_rate(
    holdout_rows: list[dict[str, Any]],
    *,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure | None = None,
    train_rows: list[dict[str, Any]] | None = None,
    top_k: int = 5,
) -> float:
    structure = structure or load_network_structure()
    affinity = build_outcome_factor_affinity(train_rows or [])
    hits = 0
    total = 0
    for row in holdout_rows:
        labeled = {factor_id for factor_id, value in row.get("factor_labels", {}).items() if int(value) == 1}
        if not labeled:
            continue
        outcome_id = row.get("outcome_id")
        if not outcome_id:
            continue
        outcome_affinity = affinity.get(outcome_id, {})
        ranked_factors = sorted(
            [factor.factor_id for factor in RISK_FACTORS],
            key=lambda factor_id: (
                outcome_affinity.get(factor_id, 0.0),
                float(cpt_payload["nodes"][factor_id]["probabilities"]["active"]),
            ),
            reverse=True,
        )
        predicted = set(ranked_factors[: max(top_k, len(labeled))])
        hits += len(labeled & predicted)
        total += len(labeled)
    return round(hits / total, 4) if total else 0.0


def outcome_brier_score(
    holdout_rows: list[dict[str, Any]],
    *,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure | None = None,
) -> float:
    structure = structure or load_network_structure()
    if not holdout_rows:
        return 0.0

    scores: list[float] = []
    outcome_ids = [outcome.outcome_id for outcome in ACCIDENT_OUTCOMES]
    for row in holdout_rows:
        true_outcome = row.get("outcome_id")
        if not true_outcome:
            continue
        probs = predict_outcome_distribution(row, cpt_payload=cpt_payload, structure=structure)
        brier = sum((probs.get(outcome_id, 0.0) - (1.0 if outcome_id == true_outcome else 0.0)) ** 2 for outcome_id in outcome_ids)
        scores.append(brier / len(outcome_ids))
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def run_l3_calibration(
    training_rows: list[dict[str, Any]],
    *,
    holdout_ratio: float = 0.2,
    alpha: float = 1.0,
    seed: int = 42,
    min_factor_hit_rate: float = 0.55,
) -> dict[str, Any]:
    train_rows, holdout_rows = split_training_rows(training_rows, holdout_ratio=holdout_ratio, seed=seed)
    cpt_payload = learn_cpt_from_training_rows(train_rows, alpha=alpha)
    structure = load_network_structure()
    hit_rate = factor_hit_rate(
        holdout_rows,
        cpt_payload=cpt_payload,
        structure=structure,
        train_rows=train_rows,
    )
    brier = outcome_brier_score(holdout_rows, cpt_payload=cpt_payload, structure=structure)
    return {
        "train_cases": len(train_rows),
        "holdout_cases": len(holdout_rows),
        "factor_hit_rate": hit_rate,
        "outcome_brier_score": brier,
        "min_factor_hit_rate": min_factor_hit_rate,
        "passed": hit_rate >= min_factor_hit_rate,
        "cpt_payload": cpt_payload,
        "outcome_factor_affinity": build_outcome_factor_affinity(train_rows),
    }
