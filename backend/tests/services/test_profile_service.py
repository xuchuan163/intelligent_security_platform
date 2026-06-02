from app.services.profiles.calculator import calculate_project_profile


def test_project_profile_includes_rule_bonus_and_level():
    result = calculate_project_profile(
        hazard_overdue_count=1,
        major_hazard_overdue_count=1,
        equipment_overdue_count=0,
        schedule_pressure_index=10,
    )

    assert result.total_risk_score >= 61
    assert result.risk_level == "high"
    assert "重大隐患超期未闭环" in result.risk_tags
