"""Bayesian L3 CPT schema and L2-derived cold-start priors (Phase 5 L3-A.3/A.4)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.bayesian.prior import (
    ACCIDENT_OUTCOMES,
    FACTOR_BY_ID,
    OUTCOME_BY_ID,
    OUTCOME_LIKELIHOOD,
    RISK_FACTORS,
)
from app.domain.bayesian.structure import BayesianNetworkStructure, load_network_structure

FACTOR_STATES: tuple[str, ...] = ("inactive", "active")
OUTCOME_STATES: tuple[str, ...] = ("unlikely", "likely")

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CPT_PRIOR_PATH = REPO_ROOT / "config" / "bayesian" / "cpt_prior.json"
DEFAULT_CPT_LEARNED_PATH = REPO_ROOT / "config" / "bayesian" / "cpt_learned.json"

DEFAULT_OUTCOME_LIKELIHOOD = 0.05


@dataclass(frozen=True)
class NodeCPT:
    node_id: str
    kind: str
    parents: tuple[str, ...]
    states: tuple[str, ...]
    probabilities: dict[str, float]


def _factor_active_prior(factor_id: str) -> float:
    factor = FACTOR_BY_ID[factor_id]
    return round(min(0.85, max(0.05, factor.prior * 4)), 4)


def _outcome_likelihood(factor_id: str, outcome_id: str) -> float:
    if outcome_id == "other":
        return 0.05
    return OUTCOME_LIKELIHOOD.get(factor_id, {}).get(outcome_id, DEFAULT_OUTCOME_LIKELIHOOD)


def build_node_cpts(structure: BayesianNetworkStructure) -> dict[str, NodeCPT]:
    tables: dict[str, NodeCPT] = {}
    for node in structure.nodes:
        parents = structure.parents_of(node.node_id)
        if node.kind == "factor":
            active_prior = _factor_active_prior(node.node_id)
            tables[node.node_id] = NodeCPT(
                node_id=node.node_id,
                kind="factor",
                parents=parents,
                states=FACTOR_STATES,
                probabilities={
                    "inactive": round(1.0 - active_prior, 4),
                    "active": active_prior,
                },
            )
            continue

        if not parents:
            base = OUTCOME_BY_ID[node.node_id].prior
            tables[node.node_id] = NodeCPT(
                node_id=node.node_id,
                kind="outcome",
                parents=parents,
                states=OUTCOME_STATES,
                probabilities={"unlikely": round(1.0 - base, 4), "likely": round(base, 4)},
            )
            continue

        # P(outcome=likely | all parents active) synthesized from L2 likelihoods.
        likelihoods = [_outcome_likelihood(parent_id, node.node_id) for parent_id in parents]
        likely = min(0.95, sum(likelihoods) / len(likelihoods) * 1.6)
        tables[node.node_id] = NodeCPT(
            node_id=node.node_id,
            kind="outcome",
            parents=parents,
            states=OUTCOME_STATES,
            probabilities={"unlikely": round(1.0 - likely, 4), "likely": round(likely, 4)},
            # parent-conditioned detail filled in metadata for training stage (L3-C).
        )
    return tables


def build_cpt_prior_payload(structure: BayesianNetworkStructure | None = None) -> dict[str, Any]:
    structure = structure or load_network_structure()
    tables = build_node_cpts(structure)
    return {
        "model_level": "L3",
        "model_version": "bayesian-l3-prior-v1",
        "structure_version": structure.version,
        "factor_count": len(RISK_FACTORS),
        "outcome_count": len(ACCIDENT_OUTCOMES),
        "nodes": {
            node_id: {
                "node_id": table.node_id,
                "kind": table.kind,
                "parents": list(table.parents),
                "states": list(table.states),
                "probabilities": table.probabilities,
            }
            for node_id, table in tables.items()
        },
    }


def write_cpt_prior_file(path: Path | None = None) -> Path:
    target = path or DEFAULT_CPT_PRIOR_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_cpt_prior_payload()
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return target


def load_cpt_prior(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_CPT_PRIOR_PATH
    return json.loads(target.read_text(encoding="utf-8"))


def cpt_learned_available(path: Path | None = None) -> bool:
    target = path or DEFAULT_CPT_LEARNED_PATH
    return target.is_file()


def load_cpt_learned(path: Path | None = None) -> dict[str, Any]:
    target = path or DEFAULT_CPT_LEARNED_PATH
    if not target.is_file():
        raise FileNotFoundError(f"Learned CPT not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))
