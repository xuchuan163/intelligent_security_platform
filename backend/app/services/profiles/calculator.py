from dataclasses import dataclass, field
from functools import lru_cache

from app.domain.dynamic_factors import dynamic_factor_evidence, evaluate_dynamic_factors
from app.domain.risk import calculate_final_score, level_for_score
from app.domain.weights import weighted_project_base_score
from app.services.rules.engine import RuleEngine


@dataclass(frozen=True)
class ProfileResult:
    total_risk_score: float
    risk_level: str
    risk_tags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    rule_triggers: list[dict] = field(default_factory=list)
    data_completeness: float = 0.0
    human_review_required: bool = False


@lru_cache(maxsize=1)
def default_rule_engine() -> RuleEngine:
    return RuleEngine.from_config()


def calculate_project_profile(
    hazard_overdue_count: int,
    major_hazard_overdue_count: int,
    equipment_overdue_count: int,
    schedule_pressure_index: float,
    project_type: str | None = None,
    night_shift_days: int = 0,
    cross_operation_count: int = 0,
    weather_alert_level: int = 0,
    rule_engine: RuleEngine | None = None,
) -> ProfileResult:
    base_score, weight_evidence = weighted_project_base_score(
        project_type,
        hazard_overdue_count=hazard_overdue_count,
        equipment_overdue_count=equipment_overdue_count,
        schedule_pressure_index=schedule_pressure_index,
    )
    facts = {
        "hazard_overdue_count": hazard_overdue_count,
        "major_hazard_overdue_count": major_hazard_overdue_count,
        "equipment_overdue_count": equipment_overdue_count,
        "schedule_pressure_index": schedule_pressure_index,
        "night_shift_days": night_shift_days,
        "cross_operation_count": cross_operation_count,
        "weather_alert_level": weather_alert_level,
    }
    dynamic_evaluation = evaluate_dynamic_factors(facts)
    factor_evidence = dynamic_factor_evidence(dynamic_evaluation)
    dynamic_tags = [trigger.factor_name for trigger in dynamic_evaluation.triggers]

    triggers = (rule_engine or default_rule_engine()).evaluate("project", facts)
    rule_bonus = sum(trigger.risk_bonus for trigger in triggers)
    tags = [*dynamic_tags, *(trigger.risk_tag for trigger in triggers)]
    evidence = [
        *weight_evidence,
        *factor_evidence,
        *(f"rule:{trigger.rule_id}" for trigger in triggers),
    ]
    rule_triggers = [_trigger_to_dict(trigger) for trigger in triggers]

    score = calculate_final_score(base_score, dynamic_evaluation.factor, rule_bonus)
    level = level_for_score(score).value

    if rule_bonus >= 20 and level in ("low", "medium"):
        level = "high"
        score = max(score, 61)

    return ProfileResult(
        total_risk_score=score,
        risk_level=level,
        risk_tags=tags,
        evidence=evidence,
        rule_triggers=rule_triggers,
        data_completeness=0.85,
        human_review_required=rule_bonus > 0,
    )


def calculate_worker_profile(
    exam_score: float | None,
    violation_count_30d: int,
    special_cert_status: str,
    health_check_status: str,
    entry_days: int,
    rule_engine: RuleEngine | None = None,
) -> ProfileResult:
    if entry_days < 7:
        return ProfileResult(
            total_risk_score=0,
            risk_level="low",
            risk_tags=["新进场观察期"],
            evidence=["entry_days < 7"],
            data_completeness=0.3,
            human_review_required=True,
        )

    base_score = 0.0
    tags: list[str] = []
    evidence: list[str] = []

    if exam_score is not None and exam_score < 60:
        base_score += 20
        tags.append("安全考核不合格")
        evidence.append("exam_score < 60")
    if violation_count_30d >= 3:
        base_score += 20
    elif violation_count_30d >= 1:
        base_score += 12

    facts = {
        "exam_score": exam_score,
        "violation_count_30d": violation_count_30d,
        "special_cert_status": special_cert_status,
        "health_check_status": health_check_status,
        "entry_days": entry_days,
    }
    triggers = (rule_engine or default_rule_engine()).evaluate("worker", facts)
    rule_bonus = sum(trigger.risk_bonus for trigger in triggers)
    tags.extend(trigger.risk_tag for trigger in triggers)
    evidence.extend(f"rule:{trigger.rule_id}" for trigger in triggers)
    rule_triggers = [_trigger_to_dict(trigger) for trigger in triggers]

    score = calculate_final_score(base_score, 1.0, rule_bonus)
    level = level_for_score(score).value

    if special_cert_status == "expired" or violation_count_30d >= 3:
        if level in ("low", "medium"):
            level = "high"
            score = max(score, 61)

    return ProfileResult(
        total_risk_score=score,
        risk_level=level,
        risk_tags=tags,
        evidence=evidence,
        rule_triggers=rule_triggers,
        data_completeness=0.8,
        human_review_required=rule_bonus > 0,
    )


def calculate_subcontractor_profile(
    hazard_overdue_count: int,
    major_hazard_overdue_count: int,
    high_risk_worker_ratio: float,
    safety_license_status: str,
    accident_history_count: int,
    rule_engine: RuleEngine | None = None,
) -> ProfileResult:
    base_score = min(60, hazard_overdue_count * 6 + high_risk_worker_ratio * 40)
    facts = {
        "hazard_overdue_count": hazard_overdue_count,
        "major_hazard_overdue_count": major_hazard_overdue_count,
        "high_risk_worker_ratio": high_risk_worker_ratio,
        "safety_license_status": safety_license_status,
        "accident_history_count": accident_history_count,
    }
    triggers = (rule_engine or default_rule_engine()).evaluate("subcontractor", facts)
    rule_bonus = sum(trigger.risk_bonus for trigger in triggers)
    tags = [trigger.risk_tag for trigger in triggers]
    evidence = [f"rule:{trigger.rule_id}" for trigger in triggers]
    rule_triggers = [_trigger_to_dict(trigger) for trigger in triggers]

    score = calculate_final_score(base_score, 1.0, rule_bonus)
    level = level_for_score(score).value

    if rule_bonus >= 20 and level in ("low", "medium"):
        level = "high"
        score = max(score, 61)

    return ProfileResult(
        total_risk_score=score,
        risk_level=level,
        risk_tags=tags,
        evidence=evidence,
        rule_triggers=rule_triggers,
        data_completeness=0.8,
        human_review_required=rule_bonus > 0,
    )


def _trigger_to_dict(trigger) -> dict:
    return {
        "rule_id": trigger.rule_id,
        "rule_name": trigger.rule_name,
        "object_type": trigger.object_type,
        "severity": trigger.severity,
        "risk_tag": trigger.risk_tag,
        "risk_bonus": trigger.risk_bonus,
        "suggested_work_order_type": trigger.suggested_work_order_type,
        "work_order_title_template": trigger.work_order_title_template,
        "work_order_priority": trigger.work_order_priority,
        "auto_create_work_order": trigger.auto_create_work_order,
        "evidence": trigger.evidence,
    }
