"""Accident-case backtest: rules/weights vs case labels (Phase 4-B.3)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models import AccidentCaseLibrary
from app.services.profiles.calculator import (
    ProfileResult,
    calculate_project_profile,
    calculate_subcontractor_profile,
    calculate_worker_profile,
    default_rule_engine,
)
from app.services.rules.engine import RuleEngine

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_PATH = _BACKEND_ROOT / "tests" / "datasets" / "case_backtest_30.jsonl"

RISK_LEVEL_ORDER: tuple[str, ...] = ("low", "medium", "high", "critical")

PROJECT_METRIC_CODES: frozenset[str] = frozenset(
    {
        "HAZARD_OVERDUE_COUNT",
        "MAJOR_HAZARD_OVERDUE_COUNT",
        "EQUIPMENT_INSPECTION_OVERDUE",
        "EQUIPMENT_ABNORMAL_COUNT",
        "CROSS_OPERATION_COUNT",
        "WEATHER_RISK_LEVEL",
        "NIGHT_WORK_PERMIT_COUNT",
        "FORMWORK_HAZARD_COUNT",
        "SCAFFOLD_INSPECTION_OVERDUE",
        "CRANE_OVERLOAD_ALARM_COUNT",
        "UTILITY_DAMAGE_RISK",
        "SITE_ENCROACHMENT_RISK",
        "TEMP_ELECTRICITY_HAZARD_COUNT",
        "HOT_WORK_PERMIT_COUNT",
        "CONFINED_SPACE_PERMIT_COUNT",
        "OPENING_UNCOVERED_COUNT",
        "RIGGING_INSPECTION_OVERDUE",
        "STRUCTURE_MONITOR_ALERT",
        "TRENCH_SUPPORT_MISSING",
        "YARD_SUPPORT_DEFECT",
        "FLOOR_OPENING_OVERLOAD",
        "EQUIPMENT_GUARD_REMOVED",
        "EQUIPMENT_OVERLOAD_ALARM_BYPASS",
        "HEAVY_LIFT_PLAN_MISSING",
        "LIFTING_PLAN_REVIEW_MISSING",
        "CRANE_OUTRIGGER_SETTLEMENT",
        "TUNNEL_SUPPORT_LAG_HOURS",
        "GROUNDWATER_LEVEL_HIGH",
        "BACKFILL_COMPACTION_FAIL",
        "ROOF_MATERIAL_UNSECURED",
        "INSTALLATION_DEFECT_COUNT",
        "PPE_INSPECTION_OVERDUE",
        "LOCKOUT_TAGOUT_VIOLATION",
        "TEMP_ELECTRICITY_PERMIT_MISSING",
        "EMERGENCY_STOP_BLOCKED",
        "WELD_INSPECTION_FAIL",
        "HYDRAULIC_HOSE_OVERDUE",
        "INSULATION_TEST_OVERDUE",
        "LIFELINE_ANCHOR_FAIL",
        "RIGGING_WEAR_ALERT",
        "SITE_TRAFFIC_VIOLATION_COUNT",
        "PPE_COMPLIANCE_RATE",
    }
)

WORKER_METRIC_CODES: frozenset[str] = frozenset(
    {
        "WORKER_VIOLATION_30D",
        "SPECIAL_CERT_EXPIRED_COUNT",
        "WORKER_SPECIAL_CERT_EXPIRED",
        "WORKER_TRAINING_PASS_RATE",
    }
)

SUBCONTRACTOR_METRIC_CODES: frozenset[str] = frozenset({"SUBCONTRACTOR_VIOLATION_30D"})

SEVERITY_MIN_RISK: dict[str, str] = {
    "一般事故": "medium",
    "险情": "medium",
    "近失": "high",
}

WEATHER_LEVEL_MAP: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True)
class BacktestEvaluation:
    case_id: str
    passed: bool
    profile_type: str
    predicted_risk_level: str
    predicted_rule_ids: tuple[str, ...]
    expected_rule_ids: tuple[str, ...]
    expected_risk_level_min: str | None
    rule_hit: bool | None
    risk_hit: bool | None
    tag_hit: bool | None
    errors: tuple[str, ...] = field(default_factory=tuple)
    mode: str = "auto"


def load_case_backtest_cases(path: str | Path = DEFAULT_DATASET_PATH) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    if not dataset_path.is_file():
        return []
    return [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)


def risk_level_at_least(actual: str, minimum: str) -> bool:
    return RISK_LEVEL_ORDER.index(actual) >= RISK_LEVEL_ORDER.index(minimum)


def _normalize_indicators(raw: Any) -> list[dict[str, Any]]:
    if not raw:
        return []
    if isinstance(raw, list):
        return [item for item in raw if isinstance(item, dict)]
    return []


def infer_profile_type(
    warning_indicators: list[dict[str, Any]],
    involved_subjects: dict[str, Any] | None = None,
) -> str:
    codes = {str(item.get("metric_code", "")) for item in warning_indicators}
    if codes & SUBCONTRACTOR_METRIC_CODES:
        return "subcontractor"
    if codes & WORKER_METRIC_CODES and not codes & PROJECT_METRIC_CODES:
        return "worker"
    subjects = (involved_subjects or {}).get("subjects") or []
    if subjects == ["worker"] and not codes & PROJECT_METRIC_CODES:
        return "worker"
    return "project"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _apply_warning_indicator(
    metric_code: str,
    value: Any,
    project_facts: dict[str, Any],
    worker_facts: dict[str, Any],
    subcontractor_facts: dict[str, Any],
) -> bool:
    mapped = False

    if metric_code == "HAZARD_OVERDUE_COUNT":
        project_facts["hazard_overdue_count"] = max(
            project_facts["hazard_overdue_count"], _as_int(value)
        )
        mapped = True
    elif metric_code == "MAJOR_HAZARD_OVERDUE_COUNT":
        project_facts["major_hazard_overdue_count"] = max(
            project_facts["major_hazard_overdue_count"], _as_int(value)
        )
        mapped = True
    elif metric_code in {
        "EQUIPMENT_INSPECTION_OVERDUE",
        "EQUIPMENT_ABNORMAL_COUNT",
        "SCAFFOLD_INSPECTION_OVERDUE",
        "RIGGING_INSPECTION_OVERDUE",
        "CRANE_OVERLOAD_ALARM_COUNT",
        "EQUIPMENT_GUARD_REMOVED",
        "EQUIPMENT_OVERLOAD_ALARM_BYPASS",
        "PPE_INSPECTION_OVERDUE",
        "INSULATION_TEST_OVERDUE",
        "HYDRAULIC_HOSE_OVERDUE",
        "RIGGING_WEAR_ALERT",
    }:
        if _as_int(value) > 0:
            project_facts["equipment_overdue_count"] = max(project_facts["equipment_overdue_count"], 1)
        mapped = True
    elif metric_code == "CROSS_OPERATION_COUNT":
        project_facts["cross_operation_count"] = max(
            project_facts["cross_operation_count"], _as_int(value)
        )
        mapped = True
    elif metric_code == "WEATHER_RISK_LEVEL":
        project_facts["weather_alert_level"] = max(
            project_facts["weather_alert_level"],
            WEATHER_LEVEL_MAP.get(str(value).lower(), 1),
        )
        mapped = True
    elif metric_code == "NIGHT_WORK_PERMIT_COUNT":
        project_facts["night_shift_days"] = max(project_facts["night_shift_days"], _as_int(value))
        mapped = True
    elif metric_code in {
        "FORMWORK_HAZARD_COUNT",
        "STRUCTURE_MONITOR_ALERT",
        "TRENCH_SUPPORT_MISSING",
        "YARD_SUPPORT_DEFECT",
        "FLOOR_OPENING_OVERLOAD",
        "BACKFILL_COMPACTION_FAIL",
        "GROUNDWATER_LEVEL_HIGH",
        "TUNNEL_SUPPORT_LAG_HOURS",
        "CRANE_OUTRIGGER_SETTLEMENT",
        "HEAVY_LIFT_PLAN_MISSING",
        "LIFTING_PLAN_REVIEW_MISSING",
        "OPENING_UNCOVERED_COUNT",
        "INSTALLATION_DEFECT_COUNT",
        "ROOF_MATERIAL_UNSECURED",
        "SITE_ENCROACHMENT_RISK",
        "TEMP_ELECTRICITY_HAZARD_COUNT",
        "TEMP_ELECTRICITY_PERMIT_MISSING",
        "LOCKOUT_TAGOUT_VIOLATION",
        "EMERGENCY_STOP_BLOCKED",
        "WELD_INSPECTION_FAIL",
        "LIFELINE_ANCHOR_FAIL",
        "UTILITY_DAMAGE_RISK",
        "HOT_WORK_PERMIT_COUNT",
        "CONFINED_SPACE_PERMIT_COUNT",
        "SITE_TRAFFIC_VIOLATION_COUNT",
    }:
        bump = 1 if isinstance(value, str) and value.lower() == "high" else max(_as_int(value), 1)
        project_facts["major_hazard_overdue_count"] = max(
            project_facts["major_hazard_overdue_count"], bump
        )
        mapped = True
    elif metric_code == "WORKER_VIOLATION_30D":
        worker_facts["violation_count_30d"] = max(worker_facts["violation_count_30d"], _as_int(value))
        mapped = True
    elif metric_code in {"SPECIAL_CERT_EXPIRED_COUNT", "WORKER_SPECIAL_CERT_EXPIRED"}:
        if _as_int(value) > 0:
            worker_facts["special_cert_status"] = "expired"
        mapped = True
    elif metric_code == "WORKER_TRAINING_PASS_RATE":
        rate = float(value)
        worker_facts["exam_score"] = min(worker_facts["exam_score"] or 100.0, rate * 100)
        mapped = True
    elif metric_code == "SUBCONTRACTOR_VIOLATION_30D":
        violations = _as_int(value)
        subcontractor_facts["high_risk_worker_ratio"] = min(
            1.0, subcontractor_facts["high_risk_worker_ratio"] + violations * 0.05
        )
        if violations >= 3:
            subcontractor_facts["accident_history_count"] = max(
                subcontractor_facts["accident_history_count"], 1
            )
        mapped = True
    elif metric_code == "PPE_COMPLIANCE_RATE":
        if float(value) < 0.85:
            project_facts["hazard_overdue_count"] = max(project_facts["hazard_overdue_count"], 1)
        mapped = True

    return mapped


def warning_indicators_to_facts(
    warning_indicators: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], int]:
    project_facts: dict[str, Any] = {
        "hazard_overdue_count": 0,
        "major_hazard_overdue_count": 0,
        "equipment_overdue_count": 0,
        "schedule_pressure_index": 15.0,
        "night_shift_days": 0,
        "cross_operation_count": 0,
        "weather_alert_level": 0,
    }
    worker_facts: dict[str, Any] = {
        "exam_score": 85.0,
        "violation_count_30d": 0,
        "special_cert_status": "valid",
        "health_check_status": "valid",
        "entry_days": 60,
    }
    subcontractor_facts: dict[str, Any] = {
        "hazard_overdue_count": 0,
        "major_hazard_overdue_count": 0,
        "high_risk_worker_ratio": 0.2,
        "safety_license_status": "valid",
        "accident_history_count": 0,
    }

    mapped_count = 0
    for item in warning_indicators:
        metric_code = str(item.get("metric_code", "")).strip()
        if not metric_code:
            continue
        if _apply_warning_indicator(
            metric_code,
            item.get("value"),
            project_facts,
            worker_facts,
            subcontractor_facts,
        ):
            mapped_count += 1

    profile_type = infer_profile_type(warning_indicators)
    if profile_type == "worker":
        return profile_type, worker_facts, mapped_count
    if profile_type == "subcontractor":
        subcontractor_facts["hazard_overdue_count"] = max(
            subcontractor_facts["hazard_overdue_count"],
            project_facts["hazard_overdue_count"],
        )
        subcontractor_facts["major_hazard_overdue_count"] = max(
            subcontractor_facts["major_hazard_overdue_count"],
            project_facts["major_hazard_overdue_count"],
        )
        return profile_type, subcontractor_facts, mapped_count
    return profile_type, project_facts, mapped_count


def infer_expected_rule_ids(profile_type: str, facts: dict[str, Any]) -> list[str]:
    expected: list[str] = []
    if profile_type == "project":
        if facts.get("major_hazard_overdue_count", 0) > 0:
            expected.append("SR-PROJ-001")
        if facts.get("equipment_overdue_count", 0) > 0:
            expected.append("SR-PROJ-004")
        if facts.get("schedule_pressure_index", 0) >= 30:
            expected.append("SR-PROJ-003")
    elif profile_type == "worker":
        if facts.get("special_cert_status") in {"expired", "missing"}:
            expected.append("SR-WORKER-001")
        violations = facts.get("violation_count_30d", 0)
        if violations >= 3:
            expected.append("SR-WORKER-005")
        elif violations >= 1:
            expected.append("SR-WORKER-004")
        if facts.get("health_check_status") == "expired":
            expected.append("SR-WORKER-002")
    elif profile_type == "subcontractor":
        if facts.get("major_hazard_overdue_count", 0) > 0:
            expected.append("SR-SUB-004")
        if facts.get("safety_license_status") in {"expired", "suspended", "missing"}:
            expected.append("SR-SUB-001")
        if facts.get("accident_history_count", 0) > 0:
            expected.append("SR-SUB-002")
    return expected


def run_profile_for_backtest(
    profile_type: str,
    facts: dict[str, Any],
    *,
    project_type: str | None = None,
    rule_engine: RuleEngine | None = None,
) -> ProfileResult:
    engine = rule_engine or default_rule_engine()
    if profile_type == "worker":
        return calculate_worker_profile(rule_engine=engine, **facts)
    if profile_type == "subcontractor":
        return calculate_subcontractor_profile(rule_engine=engine, **facts)
    return calculate_project_profile(project_type=project_type, rule_engine=engine, **facts)


def _tag_overlap(case_tags: list[str], result: ProfileResult, accident_type: str | None) -> bool:
    normalized_tags = {tag.strip() for tag in case_tags if tag and str(tag).strip()}
    predicted = {tag.strip() for tag in result.risk_tags if tag}
    if accident_type and accident_type in normalized_tags:
        normalized_tags.add(accident_type)
    return bool(normalized_tags & predicted)


def build_backtest_case_from_accident_row(row: AccidentCaseLibrary) -> dict[str, Any]:
    indicators = _normalize_indicators(row.warning_indicators)
    profile_type, facts, mapped_count = warning_indicators_to_facts(indicators)
    expected_rules = infer_expected_rule_ids(profile_type, facts)
    return {
        "case_id": row.accident_case_id,
        "accident_case_id": row.accident_case_id,
        "tenant_id": row.tenant_id,
        "profile_type": profile_type,
        "project_type": row.project_type,
        "severity": row.severity,
        "accident_type": row.accident_type,
        "tags": list(row.tags or []),
        "input": facts,
        "mapped_indicator_count": mapped_count,
        "expected": {
            "rule_ids": expected_rules,
            "risk_level_min": SEVERITY_MIN_RISK.get(row.severity),
            "tags_any": list(row.tags or []),
        },
    }


def evaluate_case_backtest(
    case: dict[str, Any],
    *,
    rule_engine: RuleEngine | None = None,
) -> BacktestEvaluation:
    case_id = str(case.get("case_id") or case.get("accident_case_id") or "unknown")
    profile_type = str(case.get("profile_type") or "project")
    facts = dict(case.get("input") or {})
    expected = dict(case.get("expected") or {})
    mode = "dataset" if case.get("input") else "auto"

    result = run_profile_for_backtest(
        profile_type,
        facts,
        project_type=case.get("project_type"),
        rule_engine=rule_engine,
    )
    triggered_rule_ids = tuple(
        sorted({str(item.get("rule_id", "")) for item in result.rule_triggers if item.get("rule_id")})
    )

    expected_rule_ids = tuple(expected.get("rule_ids") or infer_expected_rule_ids(profile_type, facts))
    expected_risk_min = expected.get("risk_level_min") or SEVERITY_MIN_RISK.get(case.get("severity"))
    case_tags = list(expected.get("tags_any") or case.get("tags") or [])

    rule_hit: bool | None = None
    if expected_rule_ids:
        rule_hit = any(rule_id in triggered_rule_ids for rule_id in expected_rule_ids)

    risk_hit: bool | None = None
    if expected_risk_min:
        risk_hit = risk_level_at_least(result.risk_level, expected_risk_min)

    tag_hit = _tag_overlap(case_tags, result, case.get("accident_type"))

    checks: list[bool] = []
    if rule_hit is not None:
        checks.append(rule_hit)
    if risk_hit is not None:
        checks.append(risk_hit)
    if not checks:
        checks.append(tag_hit)

    passed = all(checks)
    errors: list[str] = []
    if rule_hit is False:
        errors.append(
            f"expected one of {list(expected_rule_ids)} in triggered {list(triggered_rule_ids)}"
        )
    if risk_hit is False:
        errors.append(
            f"expected risk >= {expected_risk_min}, got {result.risk_level} (score={result.total_risk_score})"
        )
    if not checks:
        errors.append("no evaluable expectations and no tag overlap")

    return BacktestEvaluation(
        case_id=case_id,
        passed=passed,
        profile_type=profile_type,
        predicted_risk_level=result.risk_level,
        predicted_rule_ids=triggered_rule_ids,
        expected_rule_ids=expected_rule_ids,
        expected_risk_level_min=expected_risk_min,
        rule_hit=rule_hit,
        risk_hit=risk_hit,
        tag_hit=tag_hit,
        errors=tuple(errors),
        mode=mode,
    )


def run_case_backtest(
    cases: list[dict[str, Any]],
    *,
    rule_engine: RuleEngine | None = None,
) -> dict[str, Any]:
    evaluations = [
        evaluate_case_backtest(case, rule_engine=rule_engine) for case in cases
    ]
    passed_cases = sum(1 for item in evaluations if item.passed)
    total_cases = len(evaluations)

    rule_cases = [item for item in evaluations if item.rule_hit is not None]
    risk_cases = [item for item in evaluations if item.risk_hit is not None]
    tag_cases = [item for item in evaluations if item.tag_hit is not None]

    by_profile_type: dict[str, dict[str, int]] = {}
    for item in evaluations:
        bucket = by_profile_type.setdefault(
            item.profile_type, {"total": 0, "passed": 0}
        )
        bucket["total"] += 1
        if item.passed:
            bucket["passed"] += 1

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": total_cases - passed_cases,
        "hit_rate": _rate(passed_cases, total_cases),
        "coverage": {
            "mapped_cases": sum(
                1 for case in cases if int(case.get("mapped_indicator_count") or 0) > 0
            ),
            "total_cases": total_cases,
            "mapped_rate": _rate(
                sum(1 for case in cases if int(case.get("mapped_indicator_count") or 0) > 0),
                total_cases,
            ),
            "by_profile_type": {
                key: {
                    **value,
                    "hit_rate": _rate(value["passed"], value["total"]),
                }
                for key, value in by_profile_type.items()
            },
        },
        "rule_hit_rate": _rate(
            sum(1 for item in rule_cases if item.rule_hit),
            len(rule_cases),
        ),
        "risk_level_hit_rate": _rate(
            sum(1 for item in risk_cases if item.risk_hit),
            len(risk_cases),
        ),
        "tag_hit_rate": _rate(
            sum(1 for item in tag_cases if item.tag_hit),
            len(tag_cases),
        ),
        "evaluations": [
            {
                "case_id": item.case_id,
                "passed": item.passed,
                "profile_type": item.profile_type,
                "predicted_risk_level": item.predicted_risk_level,
                "predicted_rule_ids": list(item.predicted_rule_ids),
                "expected_rule_ids": list(item.expected_rule_ids),
                "expected_risk_level_min": item.expected_risk_level_min,
                "rule_hit": item.rule_hit,
                "risk_hit": item.risk_hit,
                "tag_hit": item.tag_hit,
                "errors": list(item.errors),
                "mode": item.mode,
            }
            for item in evaluations
        ],
    }


def run_case_backtest_from_db(
    db: Session,
    *,
    tenant_id: str | None = None,
    rule_engine: RuleEngine | None = None,
) -> dict[str, Any]:
    query = db.query(AccidentCaseLibrary).filter(AccidentCaseLibrary.status == "active")
    if tenant_id:
        query = query.filter(AccidentCaseLibrary.tenant_id == tenant_id)
    rows = query.order_by(AccidentCaseLibrary.accident_case_id.asc()).all()
    cases = [build_backtest_case_from_accident_row(row) for row in rows]
    report = run_case_backtest(cases, rule_engine=rule_engine)
    report["tenant_id"] = tenant_id
    report["source"] = "accident_case_library"
    return report
