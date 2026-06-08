"""Profile field mapping to Bayesian risk-factor evidence (§18.4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ProfileKind = Literal["project", "worker", "subcontractor"]


@dataclass(frozen=True)
class EvidenceSignal:
    factor_id: str
    strength: float
    source: ProfileKind
    field: str
    raw_value: float | str | None


def _normalize_score(value: float | None, *, cap: float = 100.0) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value) / cap))


def _risk_level_boost(risk_level: str | None) -> float:
    boosts = {"low": 0.0, "medium": 0.08, "high": 0.15, "critical": 0.22}
    return boosts.get(str(risk_level or "low"), 0.0)


def _merge_signal(
    bucket: dict[str, EvidenceSignal],
    *,
    factor_id: str,
    strength: float,
    source: ProfileKind,
    field: str,
    raw_value: float | str | None,
) -> None:
    strength = max(0.0, min(1.0, strength))
    if strength <= 0:
        return
    existing = bucket.get(factor_id)
    if existing is None or strength > existing.strength:
        bucket[factor_id] = EvidenceSignal(
            factor_id=factor_id,
            strength=strength,
            source=source,
            field=field,
            raw_value=raw_value,
        )


def extract_project_signals(profile: dict[str, Any] | None) -> list[EvidenceSignal]:
    if not profile:
        return []
    scores = profile.get("dimension_scores") or {}
    boost = _risk_level_boost(profile.get("risk_level"))
    bucket: dict[str, EvidenceSignal] = {}

    mappings: tuple[tuple[str, str], ...] = (
        ("hazard_rectification", "mgmt_rectification_gap"),
        ("hazard_rectification", "mgmt_oversight_gap"),
        ("equipment_mechanical", "machine_fault"),
        ("equipment_mechanical", "machine_maintenance_gap"),
        ("equipment_mechanical", "machine_guard_failure"),
        ("schedule_pressure", "mgmt_schedule_pressure"),
        ("subcontractor_transfer", "mgmt_subcontractor_weak"),
        ("behavior_risk", "env_cross_operation"),
        ("behavior_risk", "human_violation"),
    )
    for score_key, factor_id in mappings:
        strength = _normalize_score(scores.get(score_key)) + boost
        _merge_signal(
            bucket,
            factor_id=factor_id,
            strength=strength,
            source="project",
            field=f"dimension_scores.{score_key}",
            raw_value=scores.get(score_key),
        )

    total_score = profile.get("total_risk_score")
    if total_score is not None:
        _merge_signal(
            bucket,
            factor_id="mgmt_oversight_gap",
            strength=_normalize_score(float(total_score)) * 0.6 + boost,
            source="project",
            field="total_risk_score",
            raw_value=total_score,
        )

    return sorted(bucket.values(), key=lambda item: item.strength, reverse=True)


def extract_worker_signals(profile: dict[str, Any] | None) -> list[EvidenceSignal]:
    if not profile:
        return []
    scores = profile.get("dimension_scores") or {}
    boost = _risk_level_boost(profile.get("risk_level"))
    bucket: dict[str, EvidenceSignal] = {}

    mappings: tuple[tuple[str, str], ...] = (
        ("exam_risk", "human_training_gap"),
        ("violation_risk", "human_violation"),
        ("qualification_risk", "human_uncertified"),
        ("health_adaptation", "human_health_mismatch"),
    )
    for score_key, factor_id in mappings:
        strength = _normalize_score(scores.get(score_key)) + boost
        _merge_signal(
            bucket,
            factor_id=factor_id,
            strength=strength,
            source="worker",
            field=f"dimension_scores.{score_key}",
            raw_value=scores.get(score_key),
        )

    return sorted(bucket.values(), key=lambda item: item.strength, reverse=True)


def extract_subcontractor_signals(profile: dict[str, Any] | None) -> list[EvidenceSignal]:
    if not profile:
        return []
    scores = profile.get("dimension_scores") or {}
    boost = _risk_level_boost(profile.get("risk_level"))
    bucket: dict[str, EvidenceSignal] = {}

    mappings: tuple[tuple[str, str], ...] = (
        ("qualification_risk", "mgmt_subcontractor_weak"),
        ("worker_management", "mgmt_subcontractor_weak"),
        ("hazard_rectification", "mgmt_rectification_gap"),
        ("violation_risk", "human_violation"),
        ("accident_credit", "mgmt_oversight_gap"),
        ("equipment_management", "machine_maintenance_gap"),
    )
    for score_key, factor_id in mappings:
        strength = _normalize_score(scores.get(score_key)) + boost
        _merge_signal(
            bucket,
            factor_id=factor_id,
            strength=strength,
            source="subcontractor",
            field=f"dimension_scores.{score_key}",
            raw_value=scores.get(score_key),
        )

    high_risk_ratio = profile.get("high_risk_worker_ratio")
    if high_risk_ratio is not None:
        _merge_signal(
            bucket,
            factor_id="mgmt_subcontractor_weak",
            strength=min(1.0, float(high_risk_ratio) + boost),
            source="subcontractor",
            field="high_risk_worker_ratio",
            raw_value=high_risk_ratio,
        )

    overdue_ratio = profile.get("overdue_rectification_ratio")
    if overdue_ratio is not None:
        _merge_signal(
            bucket,
            factor_id="mgmt_rectification_gap",
            strength=min(1.0, float(overdue_ratio) + boost),
            source="subcontractor",
            field="overdue_rectification_ratio",
            raw_value=overdue_ratio,
        )

    return sorted(bucket.values(), key=lambda item: item.strength, reverse=True)


def merge_profile_signals(
    *,
    project_profile: dict[str, Any] | None,
    worker_profile: dict[str, Any] | None,
    subcontractor_profile: dict[str, Any] | None,
) -> dict[str, float]:
    """Merge evidence strengths per factor; keep max strength across profiles."""
    merged: dict[str, float] = {}
    for signal in (
        extract_project_signals(project_profile)
        + extract_worker_signals(worker_profile)
        + extract_subcontractor_signals(subcontractor_profile)
    ):
        merged[signal.factor_id] = max(merged.get(signal.factor_id, 0.0), signal.strength)
    return merged


def collect_evidence_records(
    *,
    project_profile: dict[str, Any] | None,
    worker_profile: dict[str, Any] | None,
    subcontractor_profile: dict[str, Any] | None,
    min_strength: float = 0.15,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for signal in (
        extract_project_signals(project_profile)
        + extract_worker_signals(worker_profile)
        + extract_subcontractor_signals(subcontractor_profile)
    ):
        if signal.strength < min_strength:
            continue
        records.append(
            {
                "factor_id": signal.factor_id,
                "source": signal.source,
                "field": signal.field,
                "value": signal.raw_value,
                "strength": round(signal.strength, 4),
            }
        )
    return records
