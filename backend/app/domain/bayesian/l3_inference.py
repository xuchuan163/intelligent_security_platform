"""Bayesian L3 inference: learned CPT + DAG propagation paths (Phase 5 L3-D)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.domain.bayesian.inference import _control_priorities, _resolve_outcome_id
from app.domain.bayesian.mapping import collect_evidence_records, merge_profile_signals
from app.domain.bayesian.prior import FACTOR_BY_ID, OUTCOME_BY_ID, RISK_FACTORS
from app.domain.bayesian.structure import BayesianNetworkStructure, load_network_structure
from app.domain.bayesian.outcome_probs import predict_outcome_distribution
from app.domain.bayesian.cpt import DEFAULT_CPT_LEARNED_PATH, load_cpt_learned

EVIDENCE_ACTIVE_THRESHOLD = 0.25
DEFAULT_PATH_LIMIT = 5


@dataclass(frozen=True)
class L3AttributionResult:
    model_level: str
    model_version: str
    need_human_review: bool
    project_id: str
    worker_id: str | None
    subcontractor_id: str | None
    accident_type: str | None
    risk_level: str | None
    factor_contributions: list[dict[str, Any]]
    accident_type_probabilities: list[dict[str, Any]]
    control_priorities: list[str]
    evidence: list[dict[str, Any]]
    disclaimer: str
    propagation_paths: list[dict[str, Any]]
    cpt_version: str
    structure_version: str
    calibration_hint: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_level": self.model_level,
            "model_version": self.model_version,
            "need_human_review": self.need_human_review,
            "project_id": self.project_id,
            "worker_id": self.worker_id,
            "subcontractor_id": self.subcontractor_id,
            "accident_type": self.accident_type,
            "risk_level": self.risk_level,
            "factor_contributions": self.factor_contributions,
            "accident_type_probabilities": self.accident_type_probabilities,
            "control_priorities": self.control_priorities,
            "evidence": self.evidence,
            "disclaimer": self.disclaimer,
            "propagation_paths": self.propagation_paths,
            "cpt_version": self.cpt_version,
            "structure_version": self.structure_version,
            "calibration_hint": self.calibration_hint,
        }


def _evidence_to_factor_labels(evidence_map: dict[str, float]) -> dict[str, int]:
    return {
        factor_id: 1
        for factor_id, strength in evidence_map.items()
        if strength >= EVIDENCE_ACTIVE_THRESHOLD
    }


def _factor_scores(
    evidence_map: dict[str, float],
    *,
    cpt_payload: dict[str, Any],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for factor in RISK_FACTORS:
        evidence_strength = evidence_map.get(factor.factor_id, 0.0)
        learned_active = float(cpt_payload["nodes"][factor.factor_id]["probabilities"]["active"])
        scores[factor.factor_id] = evidence_strength * 0.65 + learned_active * 0.35 + factor.prior * 0.1
    total = sum(scores.values()) or 1.0
    return {factor_id: value / total for factor_id, value in scores.items()}


def _factor_contributions(factor_scores: dict[str, float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for factor_id, contribution in sorted(factor_scores.items(), key=lambda item: item[1], reverse=True):
        factor = FACTOR_BY_ID[factor_id]
        rows.append(
            {
                "factor_id": factor_id,
                "category": factor.category,
                "label": factor.label,
                "prior": round(factor.prior, 4),
                "posterior": round(contribution, 4),
                "contribution": round(contribution * 100, 2),
            }
        )
    return rows


def _accident_probabilities(
    evidence_map: dict[str, float],
    *,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure,
    target_outcome_id: str | None = None,
) -> list[dict[str, Any]]:
    factor_labels = _evidence_to_factor_labels(evidence_map)
    distribution = predict_outcome_distribution(factor_labels, cpt_payload=cpt_payload, structure=structure)
    if target_outcome_id and target_outcome_id in distribution:
        boosted = dict(distribution)
        boosted[target_outcome_id] = min(0.95, boosted[target_outcome_id] * 1.35)
        total = sum(boosted.values()) or 1.0
        distribution = {outcome_id: value / total for outcome_id, value in boosted.items()}

    ranked = sorted(distribution.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "outcome_id": outcome_id,
            "label": OUTCOME_BY_ID[outcome_id].label,
            "probability": round(probability, 4),
        }
        for outcome_id, probability in ranked
        if outcome_id != "other"
    ]


def _top_propagation_paths(
    evidence_map: dict[str, float],
    *,
    cpt_payload: dict[str, Any],
    structure: BayesianNetworkStructure,
    target_outcome_id: str,
    limit: int = DEFAULT_PATH_LIMIT,
) -> list[dict[str, Any]]:
    parents = structure.parents_of(target_outcome_id)
    active_count = sum(1 for parent_id in parents if evidence_map.get(parent_id, 0.0) >= EVIDENCE_ACTIVE_THRESHOLD)
    outcome_node = cpt_payload["nodes"][target_outcome_id]
    bucket_key = f"active_parent_count:{active_count}"
    conditional = outcome_node.get("conditional_probabilities", {}).get(
        bucket_key,
        outcome_node["probabilities"],
    )
    outcome_likely = float(conditional["likely"])

    paths: list[dict[str, Any]] = []
    for parent_id in parents:
        evidence_strength = evidence_map.get(parent_id, 0.0)
        if evidence_strength <= 0:
            continue
        factor_active = float(cpt_payload["nodes"][parent_id]["probabilities"]["active"])
        weight = round(evidence_strength * factor_active * outcome_likely, 6)
        paths.append(
            {
                "path_id": f"{parent_id}->{target_outcome_id}",
                "nodes": [parent_id, target_outcome_id],
                "edges": [{"from": parent_id, "to": target_outcome_id, "weight": weight}],
                "weight": weight,
                "target_outcome_id": target_outcome_id,
            }
        )
    return sorted(paths, key=lambda item: item["weight"], reverse=True)[:limit]


def _calibration_hint(cpt_payload: dict[str, Any]) -> str:
    case_count = cpt_payload.get("case_count", "unknown")
    trained_at = cpt_payload.get("trained_at", "unknown")
    return (
        f"L3 CPT 基于 {case_count} 条案例训练（{trained_at}）；"
        "校准指标见 docs/algo/bayesian_l3_backtest.md；须人工复核。"
    )


def run_l3_attribution(
    *,
    project_id: str,
    project_profile: dict[str, Any] | None,
    worker_profile: dict[str, Any] | None = None,
    subcontractor_profile: dict[str, Any] | None = None,
    worker_id: str | None = None,
    subcontractor_id: str | None = None,
    accident_type: str | None = None,
    cpt_payload: dict[str, Any] | None = None,
    structure: BayesianNetworkStructure | None = None,
    cpt_path: Path | None = None,
) -> L3AttributionResult:
    cpt_payload = cpt_payload or load_cpt_learned(cpt_path or DEFAULT_CPT_LEARNED_PATH)
    structure = structure or load_network_structure()

    evidence_map = merge_profile_signals(
        project_profile=project_profile,
        worker_profile=worker_profile,
        subcontractor_profile=subcontractor_profile,
    )
    factor_scores = _factor_scores(evidence_map, cpt_payload=cpt_payload)
    contributions = _factor_contributions(factor_scores)
    target_outcome_id = _resolve_outcome_id(accident_type)
    accident_probs = _accident_probabilities(
        evidence_map,
        cpt_payload=cpt_payload,
        structure=structure,
        target_outcome_id=target_outcome_id,
    )
    evidence = collect_evidence_records(
        project_profile=project_profile,
        worker_profile=worker_profile,
        subcontractor_profile=subcontractor_profile,
    )

    path_target = target_outcome_id or accident_probs[0]["outcome_id"]
    propagation_paths = _top_propagation_paths(
        evidence_map,
        cpt_payload=cpt_payload,
        structure=structure,
        target_outcome_id=path_target,
    )

    risk_level = None
    if project_profile:
        risk_level = project_profile.get("risk_level")
    elif worker_profile:
        risk_level = worker_profile.get("risk_level")
    elif subcontractor_profile:
        risk_level = subcontractor_profile.get("risk_level")

    return L3AttributionResult(
        model_level="L3",
        model_version=str(cpt_payload.get("model_version", "bayesian-l3-unknown")),
        need_human_review=True,
        project_id=project_id,
        worker_id=worker_id,
        subcontractor_id=subcontractor_id,
        accident_type=accident_type,
        risk_level=risk_level,
        factor_contributions=contributions,
        accident_type_probabilities=accident_probs,
        control_priorities=_control_priorities(contributions),
        evidence=evidence,
        disclaimer=(
            "L3 案例驱动 CPT 归因结果仅供风险研判参考，不得作为处罚、清退或停工的唯一依据；"
            "关键结论须结合规则触发记录、传播路径与现场证据人工复核。"
        ),
        propagation_paths=propagation_paths,
        cpt_version=str(cpt_payload.get("model_version", "bayesian-l3-unknown")),
        structure_version=str(cpt_payload.get("structure_version", structure.version)),
        calibration_hint=_calibration_hint(cpt_payload),
    )
