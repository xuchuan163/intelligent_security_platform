"""Map accident-case text and indicators to Bayesian factor labels (Phase 5 L3-B)."""

from __future__ import annotations

from typing import Any

from app.domain.bayesian.prior import ACCIDENT_TYPE_ALIASES, FACTOR_BY_ID
from app.services.cases.backtest import infer_profile_type, warning_indicators_to_facts

# keyword -> factor_id (longer phrases first when matching)
TEXT_FACTOR_RULES: tuple[tuple[str, str], ...] = (
    ("安全带", "human_violation"),
    ("培训", "human_training_gap"),
    ("教育", "human_training_gap"),
    ("交底", "method_briefing_gap"),
    ("专项方案", "method_plan_missing"),
    ("方案缺失", "method_plan_missing"),
    ("作业票", "method_permit_irregular"),
    ("临电", "method_permit_irregular"),
    ("触电", "human_uncertified"),
    ("配电", "machine_fault"),
    ("设备", "machine_fault"),
    ("点检", "machine_maintenance_gap"),
    ("检验", "machine_maintenance_gap"),
    ("防护", "machine_guard_failure"),
    ("护栏", "machine_guard_failure"),
    ("临边", "machine_guard_failure"),
    ("孔洞", "machine_guard_failure"),
    ("易燃", "material_fire_risk"),
    ("火灾", "material_fire_risk"),
    ("堆码", "material_stack_unstable"),
    ("交叉作业", "env_cross_operation"),
    ("吊装", "env_cross_operation"),
    ("夜间", "env_night_lighting"),
    ("照明", "env_night_lighting"),
    ("雨季", "env_weather"),
    ("降雨", "env_weather"),
    ("大风", "env_weather"),
    ("疲劳", "human_fatigue"),
    ("健康", "human_health_mismatch"),
    ("体检", "human_health_mismatch"),
    ("证书", "human_uncertified"),
    ("特种", "human_uncertified"),
    ("违规", "human_violation"),
    ("分包", "mgmt_subcontractor_weak"),
    ("整改", "mgmt_rectification_gap"),
    ("超期", "mgmt_rectification_gap"),
    ("巡检", "mgmt_oversight_gap"),
    ("旁站", "mgmt_oversight_gap"),
    ("监管", "mgmt_oversight_gap"),
    ("赶工", "mgmt_schedule_pressure"),
    ("工期", "mgmt_schedule_pressure"),
    ("投入", "mgmt_safety_investment"),
)

INDICATOR_FACTOR_HINTS: dict[str, str] = {
    "HAZARD_OVERDUE_COUNT": "mgmt_rectification_gap",
    "MAJOR_HAZARD_OVERDUE_COUNT": "mgmt_rectification_gap",
    "EQUIPMENT_INSPECTION_OVERDUE": "machine_maintenance_gap",
    "EQUIPMENT_ABNORMAL_COUNT": "machine_fault",
    "CROSS_OPERATION_COUNT": "env_cross_operation",
    "NIGHT_WORK_PERMIT_COUNT": "env_night_lighting",
    "WORKER_SPECIAL_CERT_EXPIRED": "human_uncertified",
    "SPECIAL_CERT_EXPIRED_COUNT": "human_uncertified",
    "WORKER_VIOLATION_30D": "human_violation",
    "WORKER_TRAINING_PASS_RATE": "human_training_gap",
    "SUBCONTRACTOR_VIOLATION_30D": "mgmt_subcontractor_weak",
    "OPENING_UNCOVERED_COUNT": "machine_guard_failure",
    "RIGGING_INSPECTION_OVERDUE": "machine_maintenance_gap",
    "SITE_ENCROACHMENT_RISK": "mgmt_oversight_gap",
    "TEMP_ELECTRICITY_HAZARD_COUNT": "method_permit_irregular",
    "HOT_WORK_PERMIT_COUNT": "material_fire_risk",
}


def resolve_outcome_id(accident_type: str | None) -> str | None:
    if not accident_type:
        return None
    normalized = accident_type.strip()
    if normalized in ACCIDENT_TYPE_ALIASES:
        return ACCIDENT_TYPE_ALIASES[normalized]
    return "other"


def _normalize_tags(tags: Any) -> list[str]:
    if isinstance(tags, list):
        return [str(item).strip() for item in tags if str(item).strip()]
    if isinstance(tags, dict):
        values = tags.get("tags")
        if isinstance(values, list):
            return [str(item).strip() for item in values if str(item).strip()]
    return []


def _apply_text_rules(text: str, labels: dict[str, int]) -> None:
    lowered = text.lower()
    for keyword, factor_id in TEXT_FACTOR_RULES:
        if keyword.lower() in lowered:
            labels[factor_id] = 1


def extract_factor_labels_from_text(
    *,
    direct_cause: str | None,
    indirect_cause: str | None,
    tags: Any = None,
) -> dict[str, int]:
    labels: dict[str, int] = {}
    chunks = [
        direct_cause or "",
        indirect_cause or "",
        " ".join(_normalize_tags(tags)),
    ]
    for chunk in chunks:
        _apply_text_rules(chunk, labels)
    return {factor_id: 1 for factor_id in labels if factor_id in FACTOR_BY_ID}


def extract_factor_labels_from_indicators(
    warning_indicators: list[dict[str, Any]] | None,
) -> dict[str, int]:
    labels: dict[str, int] = {}
    if not warning_indicators:
        return labels

    for item in warning_indicators:
        if not isinstance(item, dict):
            continue
        metric_code = str(item.get("metric_code", "")).strip()
        factor_id = INDICATOR_FACTOR_HINTS.get(metric_code)
        if factor_id:
            labels[factor_id] = 1

    profile_type, _, mapped_count = warning_indicators_to_facts(warning_indicators)
    if mapped_count > 0 and profile_type == "project":
        labels.setdefault("mgmt_rectification_gap", 1)
    if mapped_count > 0 and profile_type == "worker":
        labels.setdefault("human_violation", 1)
    if mapped_count > 0 and profile_type == "subcontractor":
        labels.setdefault("mgmt_subcontractor_weak", 1)

    return labels


def merge_factor_labels(*label_maps: dict[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for label_map in label_maps:
        for factor_id, value in label_map.items():
            if factor_id in FACTOR_BY_ID:
                merged[factor_id] = max(merged.get(factor_id, 0), int(value))
    return merged


def label_accident_case_row(row: dict[str, Any]) -> dict[str, Any]:
    warning_indicators = row.get("warning_indicators")
    if isinstance(warning_indicators, dict):
        warning_indicators = warning_indicators.get("items") or warning_indicators.get("indicators")
    if not isinstance(warning_indicators, list):
        warning_indicators = []

    text_labels = extract_factor_labels_from_text(
        direct_cause=row.get("direct_cause"),
        indirect_cause=row.get("indirect_cause"),
        tags=row.get("tags"),
    )
    indicator_labels = extract_factor_labels_from_indicators(warning_indicators)
    factor_labels = merge_factor_labels(text_labels, indicator_labels)
    outcome_id = resolve_outcome_id(row.get("accident_type"))
    profile_type = infer_profile_type(warning_indicators) if warning_indicators else "project"

    return {
        "case_id": row.get("accident_case_id") or row.get("case_id"),
        "outcome_id": outcome_id,
        "factor_labels": factor_labels,
        "profile_type": profile_type,
        "warning_indicators": warning_indicators,
        "accident_type": row.get("accident_type"),
    }
