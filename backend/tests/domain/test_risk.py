from app.domain.risk import RiskLevel, calculate_final_score, level_for_score


def test_calculate_final_score_caps_at_100():
    score = calculate_final_score(base_score=80, dynamic_factor=1.5, rule_bonus=30)
    assert score == 100


def test_level_for_score_uses_documented_thresholds():
    assert level_for_score(20) == RiskLevel.LOW
    assert level_for_score(45) == RiskLevel.MEDIUM
    assert level_for_score(72) == RiskLevel.HIGH
    assert level_for_score(90) == RiskLevel.CRITICAL
