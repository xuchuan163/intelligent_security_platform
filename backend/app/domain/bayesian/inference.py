"""Bayesian L2 inference: expert prior + profile evidence (Phase 4-D)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.bayesian.mapping import collect_evidence_records, merge_profile_signals
from app.domain.bayesian.prior import (
    ACCIDENT_OUTCOMES,
    ACCIDENT_TYPE_ALIASES,
    FACTOR_BY_ID,
    MODEL_LEVEL,
    MODEL_VERSION,
    OUTCOME_BY_ID,
    OUTCOME_LIKELIHOOD,
    RISK_FACTORS,
)


@dataclass(frozen=True)
class AttributionResult:
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
        }


def _resolve_outcome_id(accident_type: str | None) -> str | None:
    if not accident_type:
        return None
    normalized = accident_type.strip()
    if normalized in OUTCOME_BY_ID:
        return normalized
    return ACCIDENT_TYPE_ALIASES.get(normalized)


def _factor_weights(evidence: dict[str, float]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for factor in RISK_FACTORS:
        signal = evidence.get(factor.factor_id, 0.0)
        # Blend expert prior with profile evidence; retain prior mass when evidence is weak.
        weights[factor.factor_id] = factor.prior * (0.35 + 0.65 * signal)
    total = sum(weights.values()) or 1.0
    return {factor_id: value / total for factor_id, value in weights.items()}


def _accident_probabilities(
    factor_weights: dict[str, float],
    *,
    target_outcome_id: str | None = None,
) -> list[dict[str, Any]]:
    raw_scores: dict[str, float] = {}
    for outcome in ACCIDENT_OUTCOMES:
        if outcome.outcome_id == "other":
            continue
        score = outcome.prior
        for factor_id, weight in factor_weights.items():
            likelihood = OUTCOME_LIKELIHOOD.get(factor_id, {}).get(outcome.outcome_id, 0.05)
            score += weight * likelihood
        if target_outcome_id and outcome.outcome_id == target_outcome_id:
            score *= 1.35
        raw_scores[outcome.outcome_id] = score

    total = sum(raw_scores.values()) or 1.0
    ranked = sorted(raw_scores.items(), key=lambda item: item[1], reverse=True)
    return [
        {
            "outcome_id": outcome_id,
            "label": OUTCOME_BY_ID[outcome_id].label,
            "probability": round(score / total, 4),
        }
        for outcome_id, score in ranked
    ]


def _factor_contributions(factor_weights: dict[str, float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for factor_id, contribution in sorted(factor_weights.items(), key=lambda item: item[1], reverse=True):
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


def _control_priorities(contributions: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    priorities: list[str] = []
    for row in contributions[:limit]:
        priorities.append(f"优先管控：{row['category']}-{row['label']}（贡献 {row['contribution']}%）")
    return priorities


def run_l2_attribution(
    *,
    project_id: str,
    project_profile: dict[str, Any] | None,
    worker_profile: dict[str, Any] | None = None,
    subcontractor_profile: dict[str, Any] | None = None,
    worker_id: str | None = None,
    subcontractor_id: str | None = None,
    accident_type: str | None = None,
) -> AttributionResult:
    evidence_map = merge_profile_signals(
        project_profile=project_profile,
        worker_profile=worker_profile,
        subcontractor_profile=subcontractor_profile,
    )
    factor_weights = _factor_weights(evidence_map)
    contributions = _factor_contributions(factor_weights)
    target_outcome_id = _resolve_outcome_id(accident_type)
    accident_probs = _accident_probabilities(factor_weights, target_outcome_id=target_outcome_id)
    evidence = collect_evidence_records(
        project_profile=project_profile,
        worker_profile=worker_profile,
        subcontractor_profile=subcontractor_profile,
    )

    risk_level = None
    if project_profile:
        risk_level = project_profile.get("risk_level")
    elif worker_profile:
        risk_level = worker_profile.get("risk_level")
    elif subcontractor_profile:
        risk_level = subcontractor_profile.get("risk_level")

    return AttributionResult(
        model_level=MODEL_LEVEL,
        model_version=MODEL_VERSION,
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
            "L2 专家先验归因结果仅供风险研判参考，不得作为处罚、清退或停工的唯一依据；"
            "关键结论须结合规则触发记录与现场证据人工复核。"
        ),
    )
