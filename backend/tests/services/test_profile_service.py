import json
from pathlib import Path

from app.services.profiles.calculator import (
    calculate_project_profile,
    calculate_subcontractor_profile,
    calculate_worker_profile,
)
from app.services.rules.engine import RuleCondition, RuleDefinition, RuleEngine

PROFILE_ALGO_DATASET = Path(__file__).resolve().parents[1] / "datasets" / "profile_algo_20.jsonl"


def _run_profile_algo_case(row: dict):
    payload = row["input"]
    if row["profile_type"] == "project":
        return calculate_project_profile(**payload)
    if row["profile_type"] == "worker":
        return calculate_worker_profile(**payload)
    return calculate_subcontractor_profile(**payload)


def test_profile_algorithm_dataset_has_20_documented_cases():
    rows = [json.loads(line) for line in PROFILE_ALGO_DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(rows) == 20
    assert {row["profile_type"] for row in rows} == {"project", "worker", "subcontractor"}
    for row in rows:
        assert {"case_id", "profile_type", "input", "expected"} <= set(row)
        assert row["expected"]["risk_level"] in {"low", "medium", "high", "critical"}


def test_profile_algorithm_dataset_cases_match_expected_risk_levels():
    rows = [json.loads(line) for line in PROFILE_ALGO_DATASET.read_text(encoding="utf-8").splitlines() if line.strip()]

    mismatches: list[str] = []
    for row in rows:
        result = _run_profile_algo_case(row)
        expected = row["expected"]["risk_level"]
        if result.risk_level != expected:
            mismatches.append(
                f"{row['case_id']}: expected {expected}, got {result.risk_level} (score={result.total_risk_score})"
            )

    assert not mismatches, "profile_algo_20 mismatches:\n" + "\n".join(mismatches)


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


def test_project_profile_uses_injected_rule_engine():
    engine = RuleEngine(
        [
            RuleDefinition(
                rule_id="SR-TEST-001",
                object_type="project",
                rule_name="测试规则",
                severity="high",
                risk_tag="测试规则标签",
                condition=RuleCondition(
                    field="major_hazard_overdue_count",
                    operator=">",
                    value=0,
                ),
                risk_bonus=35,
                suggested_work_order_type="hazard_rectification",
            )
        ]
    )

    result = calculate_project_profile(
        hazard_overdue_count=0,
        major_hazard_overdue_count=1,
        equipment_overdue_count=0,
        schedule_pressure_index=0,
        rule_engine=engine,
    )

    assert result.total_risk_score == 61
    assert result.risk_tags == ["重大隐患未闭环", "测试规则标签"]
    assert "factor:DF-HZD-001" in result.evidence
    assert result.evidence[-1] == "rule:SR-TEST-001"


def test_subcontractor_profile_uses_yaml_rule_engine():
    result = calculate_subcontractor_profile(
        hazard_overdue_count=1,
        major_hazard_overdue_count=1,
        high_risk_worker_ratio=0.5,
        safety_license_status="expired",
        accident_history_count=1,
    )

    assert result.risk_level in {"high", "critical"}
    assert result.evidence == ["rule:SR-SUB-004", "rule:SR-SUB-001", "rule:SR-SUB-002"]
    assert {trigger["rule_id"] for trigger in result.rule_triggers} == {
        "SR-SUB-004",
        "SR-SUB-001",
        "SR-SUB-002",
    }
