from app.services.profiles.calculator import calculate_project_profile


def test_project_type_changes_weighted_base_score():
    baseline = calculate_project_profile(
        hazard_overdue_count=2,
        major_hazard_overdue_count=0,
        equipment_overdue_count=0,
        schedule_pressure_index=20,
        project_type="housing",
    )
    infrastructure = calculate_project_profile(
        hazard_overdue_count=2,
        major_hazard_overdue_count=0,
        equipment_overdue_count=0,
        schedule_pressure_index=20,
        project_type="infrastructure",
    )

    assert infrastructure.total_risk_score > baseline.total_risk_score
    assert any(item.startswith("weight:project_type:") for item in baseline.evidence)
    assert not baseline.rule_triggers


def test_none_project_type_preserves_legacy_base_formula():
    result = calculate_project_profile(
        hazard_overdue_count=2,
        major_hazard_overdue_count=0,
        equipment_overdue_count=0,
        schedule_pressure_index=18,
        project_type=None,
    )

    assert result.total_risk_score == 34.0
    assert result.risk_level == "medium"
    assert not any(item.startswith("weight:project_type:") for item in result.evidence)
    assert not result.rule_triggers


def test_missing_project_type_differs_from_housing_coefficients():
    neutral = calculate_project_profile(
        hazard_overdue_count=2,
        major_hazard_overdue_count=0,
        equipment_overdue_count=1,
        schedule_pressure_index=18,
        project_type=None,
    )
    explicit_default = calculate_project_profile(
        hazard_overdue_count=2,
        major_hazard_overdue_count=0,
        equipment_overdue_count=1,
        schedule_pressure_index=18,
        project_type="housing",
    )

    # housing schedule_pressure is 1.0; hazard/equipment coeffs differ from neutral 1.0
    assert neutral.total_risk_score != explicit_default.total_risk_score
