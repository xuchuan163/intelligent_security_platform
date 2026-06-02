from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def calculate_final_score(base_score: float, dynamic_factor: float, rule_bonus: float) -> float:
    raw_score = base_score * dynamic_factor + rule_bonus
    return round(min(100, max(0, raw_score)), 2)


def level_for_score(score: float) -> RiskLevel:
    if score <= 30:
        return RiskLevel.LOW
    if score <= 60:
        return RiskLevel.MEDIUM
    if score <= 80:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL
