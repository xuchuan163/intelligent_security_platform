from pathlib import Path

import pytest

from app.domain.dynamic_factors import evaluate_dynamic_factors, load_dynamic_factor_config


def test_dynamic_factors_yaml_loads_sch_wea_hzd_groups():
    config = load_dynamic_factor_config()

    assert config.version == "1.0.0"
    assert config.base_factor == pytest.approx(1.0)
    assert config.max_factor == pytest.approx(1.5)
    codes = {factor.factor_code for factor in config.factors}
    assert codes == {
        "DF-SCH-001",
        "DF-SCH-002",
        "DF-SCH-003",
        "DF-WEA-001",
        "DF-HZD-001",
    }


def test_evaluate_dynamic_factors_sums_deltas_with_cap():
    config = load_dynamic_factor_config()
    evaluation = evaluate_dynamic_factors(
        {
            "schedule_pressure_index": 35,
            "night_shift_days": 4,
            "cross_operation_count": 2,
            "weather_alert_level": 2,
            "major_hazard_overdue_count": 1,
        },
        config=config,
    )

    assert evaluation.factor == pytest.approx(1.5)
    assert {trigger.factor_code for trigger in evaluation.triggers} == {
        "DF-SCH-001",
        "DF-SCH-002",
        "DF-SCH-003",
        "DF-WEA-001",
        "DF-HZD-001",
    }


def test_evaluate_dynamic_factors_returns_neutral_when_no_match():
    evaluation = evaluate_dynamic_factors(
        {
            "schedule_pressure_index": 10,
            "night_shift_days": 0,
            "cross_operation_count": 0,
            "weather_alert_level": 0,
            "major_hazard_overdue_count": 0,
        }
    )

    assert evaluation.factor == 1.0
    assert evaluation.triggers == ()


def test_exclusive_group_uses_max_delta_only(tmp_path: Path):
    config_path = tmp_path / "dynamic_factors.yaml"
    config_path.write_text(
        """
version: "test"
base_factor: 1.0
max_factor: 1.5
exclusive_groups:
  - DF-WEA
factors:
  - factor_code: DF-WEA-001
    group: DF-WEA
    factor_name: 橙色预警
    field: weather_alert_level
    operator: ">="
    value: 2
    delta: 0.20
  - factor_code: DF-WEA-002
    group: DF-WEA
    factor_name: 红色预警
    field: weather_alert_level
    operator: ">="
    value: 3
    delta: 0.30
""".strip(),
        encoding="utf-8",
    )
    config = load_dynamic_factor_config(config_path)
    evaluation = evaluate_dynamic_factors({"weather_alert_level": 3}, config=config)

    assert evaluation.factor == pytest.approx(1.3)
    assert len(evaluation.triggers) == 2
