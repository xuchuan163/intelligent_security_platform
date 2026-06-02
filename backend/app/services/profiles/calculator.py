from dataclasses import dataclass, field
from app.domain.risk import calculate_final_score, level_for_score


@dataclass(frozen=True)
class ProfileResult:
    total_risk_score: float
    risk_level: str
    risk_tags: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    data_completeness: float = 0.0
    human_review_required: bool = False


def calculate_project_profile(
    hazard_overdue_count: int,
    major_hazard_overdue_count: int,
    equipment_overdue_count: int,
    schedule_pressure_index: float,
) -> ProfileResult:
    base_score = min(60, hazard_overdue_count * 8 + equipment_overdue_count * 10 + schedule_pressure_index)
    rule_bonus = 0.0
    tags: list[str] = []
    evidence: list[str] = []

    if major_hazard_overdue_count > 0:
        rule_bonus += 20
        tags.append("重大隐患超期未闭环")
        evidence.append("rule:SR-PROJ-001")
    if equipment_overdue_count > 0:
        rule_bonus += 25
        tags.append("特种设备超期未检")
        evidence.append("rule:SR-PROJ-004")

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
        data_completeness=0.85,
        human_review_required=rule_bonus > 0,
    )


def calculate_worker_profile(
    exam_score: float | None,
    violation_count_30d: int,
    special_cert_status: str,
    health_check_status: str,
    entry_days: int,
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
    rule_bonus = 0.0
    tags: list[str] = []
    evidence: list[str] = []

    if exam_score is not None and exam_score < 60:
        base_score += 20
        tags.append("安全考核不合格")
        evidence.append("exam_score < 60")
    if violation_count_30d >= 3:
        base_score += 20
        rule_bonus += 15
        tags.append("频繁违规")
        evidence.append("rule:SR-WORKER-005")
    elif violation_count_30d >= 1:
        base_score += 12
        rule_bonus += 10
        tags.append("近期违规")
        evidence.append("rule:SR-WORKER-004")

    if special_cert_status in ("expired", "missing"):
        rule_bonus += 25
        tags.append("特种作业证异常")
        evidence.append("rule:SR-WORKER-001")

    if health_check_status == "expired":
        rule_bonus += 15
        tags.append("体检过期")
        evidence.append("rule:SR-WORKER-002")

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
        data_completeness=0.8,
        human_review_required=rule_bonus > 0,
    )


def calculate_subcontractor_profile(
    hazard_overdue_count: int,
    major_hazard_overdue_count: int,
    high_risk_worker_ratio: float,
    safety_license_status: str,
    accident_history_count: int,
) -> ProfileResult:
    base_score = min(60, hazard_overdue_count * 6 + high_risk_worker_ratio * 40)
    rule_bonus = 0.0
    tags: list[str] = []
    evidence: list[str] = []

    if major_hazard_overdue_count > 0:
        rule_bonus += 20
        tags.append("重大隐患超期未整改")
        evidence.append("rule:SR-SUB-004")
    if safety_license_status == "expired":
        rule_bonus += 30
        tags.append("安全生产许可证失效")
        evidence.append("rule:SR-SUB-001")
    if accident_history_count > 0:
        tags.append("存在历史事故")
        base_score += 15
        evidence.append("accident_history")

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
        data_completeness=0.8,
        human_review_required=rule_bonus > 0,
    )
