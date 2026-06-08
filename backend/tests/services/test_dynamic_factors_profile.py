from app.services.profiles.calculator import calculate_project_profile


def test_dynamic_factors_increase_project_score_without_rules():
    baseline = calculate_project_profile(
        hazard_overdue_count=2,
        major_hazard_overdue_count=0,
        equipment_overdue_count=0,
        schedule_pressure_index=18,
    )
    with_factors = calculate_project_profile(
        hazard_overdue_count=2,
        major_hazard_overdue_count=0,
        equipment_overdue_count=0,
        schedule_pressure_index=30,
        night_shift_days=4,
        cross_operation_count=2,
    )

    assert with_factors.total_risk_score > baseline.total_risk_score
    assert "赶工期" in with_factors.risk_tags
    assert any(item.startswith("factor:DF-SCH-") for item in with_factors.evidence)


def test_major_hazard_applies_df_hzd_and_rule_together():
    result = calculate_project_profile(
        hazard_overdue_count=1,
        major_hazard_overdue_count=1,
        equipment_overdue_count=0,
        schedule_pressure_index=10,
    )

    assert "重大隐患未闭环" in result.risk_tags
    assert "factor:DF-HZD-001" in result.evidence
    assert "rule:SR-PROJ-001" in result.evidence
    assert result.risk_level == "high"


def test_weather_alert_level_triggers_df_wea():
    result = calculate_project_profile(
        hazard_overdue_count=0,
        major_hazard_overdue_count=0,
        equipment_overdue_count=0,
        schedule_pressure_index=10,
        weather_alert_level=2,
    )

    assert "极端天气" in result.risk_tags
    assert "factor:DF-WEA-001" in result.evidence
