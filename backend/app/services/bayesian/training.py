"""Bayesian L3 CPT training from labeled accident cases (Phase 5 L3-C.1)."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any

from app.domain.bayesian.cpt import FACTOR_STATES, OUTCOME_STATES, load_cpt_prior
from app.domain.bayesian.prior import ACCIDENT_OUTCOMES, RISK_FACTORS
from app.domain.bayesian.structure import BayesianNetworkStructure, load_network_structure

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CPT_LEARNED_PATH = REPO_ROOT / "config" / "bayesian" / "cpt_learned.json"
DEFAULT_MODEL_VERSION = "bayesian-l3-v1.0.0"


def _laplace_probability(count: int, total: int, *, alpha: float, state_count: int) -> float:
    return round((count + alpha) / (total + alpha * state_count), 4)


def _state_probabilities(
    positive_count: int,
    total: int,
    *,
    alpha: float,
    positive_state: str,
    negative_state: str,
) -> dict[str, float]:
    positive = _laplace_probability(positive_count, total, alpha=alpha, state_count=2)
    return {negative_state: round(1.0 - positive, 4), positive_state: positive}


def _active_parent_count(factor_labels: dict[str, int], parents: tuple[str, ...]) -> int:
    return sum(1 for parent_id in parents if int(factor_labels.get(parent_id, 0)) == 1)


def learn_cpt_from_training_rows(
    training_rows: list[dict[str, Any]],
    *,
    structure: BayesianNetworkStructure | None = None,
    prior_payload: dict[str, Any] | None = None,
    alpha: float = 1.0,
    model_version: str = DEFAULT_MODEL_VERSION,
) -> dict[str, Any]:
    if not training_rows:
        raise ValueError("training_rows must not be empty")

    structure = structure or load_network_structure()
    prior_payload = prior_payload or load_cpt_prior()
    total_cases = len(training_rows)
    trained_at = dt.datetime.now(dt.timezone.utc).isoformat()
    nodes: dict[str, Any] = {}

    for factor in RISK_FACTORS:
        active_count = sum(
            1 for row in training_rows if int(row.get("factor_labels", {}).get(factor.factor_id, 0)) == 1
        )
        nodes[factor.factor_id] = {
            "node_id": factor.factor_id,
            "kind": "factor",
            "parents": [],
            "states": list(FACTOR_STATES),
            "probabilities": _state_probabilities(
                active_count,
                total_cases,
                alpha=alpha,
                positive_state="active",
                negative_state="inactive",
            ),
        }

    for outcome in ACCIDENT_OUTCOMES:
        parents = structure.parents_of(outcome.outcome_id)
        likely_count = sum(1 for row in training_rows if row.get("outcome_id") == outcome.outcome_id)
        marginal = _state_probabilities(
            likely_count,
            total_cases,
            alpha=alpha,
            positive_state="likely",
            negative_state="unlikely",
        )
        conditional: dict[str, dict[str, float]] = {}
        if parents:
            for active_count in range(len(parents) + 1):
                bucket_rows = [
                    row
                    for row in training_rows
                    if _active_parent_count(row.get("factor_labels", {}), parents) == active_count
                ]
                if not bucket_rows:
                    continue
                bucket_likely = sum(
                    1 for row in bucket_rows if row.get("outcome_id") == outcome.outcome_id
                )
                conditional[f"active_parent_count:{active_count}"] = _state_probabilities(
                    bucket_likely,
                    len(bucket_rows),
                    alpha=alpha,
                    positive_state="likely",
                    negative_state="unlikely",
                )

        nodes[outcome.outcome_id] = {
            "node_id": outcome.outcome_id,
            "kind": "outcome",
            "parents": list(parents),
            "states": list(OUTCOME_STATES),
            "probabilities": marginal,
            "conditional_probabilities": conditional,
        }

    return {
        "model_level": "L3",
        "model_version": model_version,
        "structure_version": structure.version,
        "prior_version": prior_payload.get("model_version"),
        "trained_at": trained_at,
        "case_count": total_cases,
        "training_alpha": alpha,
        "factor_count": len(RISK_FACTORS),
        "outcome_count": len(ACCIDENT_OUTCOMES),
        "nodes": nodes,
    }


def write_cpt_learned_file(
    payload: dict[str, Any],
    path: Path | None = None,
) -> Path:
    target = path or DEFAULT_CPT_LEARNED_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_cpt_learned(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_CPT_LEARNED_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def build_training_rows_from_seeds() -> list[dict[str, Any]]:
    from app.domain.bayesian.case_labels import label_accident_case_row
    from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS

    return [label_accident_case_row(seed) for seed in ACCIDENT_CASE_SEEDS]
