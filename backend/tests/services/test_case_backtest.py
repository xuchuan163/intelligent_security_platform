"""Case backtest service tests (Phase 4-B.3 / 4-B.4)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base
from app.services.cases.backtest import (
    DEFAULT_DATASET_PATH,
    build_backtest_case_from_accident_row,
    evaluate_case_backtest,
    infer_expected_rule_ids,
    load_case_backtest_cases,
    run_case_backtest,
    run_case_backtest_from_db,
    warning_indicators_to_facts,
)
from app.services.cases.seed_cases import seed_accident_cases

MIN_DB_HIT_RATE = 0.6
MIN_DATASET_HIT_RATE = 1.0
REQUIRED_DATASET_FIELDS = {"case_id", "profile_type", "input", "expected"}
VALID_PROFILE_TYPES = {"project", "worker", "subcontractor"}
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_warning_indicators_map_to_project_rule_facts():
    profile_type, facts, mapped_count = warning_indicators_to_facts(
        [
            {"metric_code": "MAJOR_HAZARD_OVERDUE_COUNT", "value": 1},
            {"metric_code": "EQUIPMENT_INSPECTION_OVERDUE", "value": 1},
        ]
    )

    assert profile_type == "project"
    assert mapped_count == 2
    assert facts["major_hazard_overdue_count"] == 1
    assert facts["equipment_overdue_count"] == 1
    assert infer_expected_rule_ids(profile_type, facts) == ["SR-PROJ-001", "SR-PROJ-004"]


def test_evaluate_case_backtest_passes_when_rules_and_risk_match():
    case = {
        "case_id": "BT-UNIT-001",
        "profile_type": "project",
        "input": {
            "hazard_overdue_count": 1,
            "major_hazard_overdue_count": 1,
            "equipment_overdue_count": 0,
            "schedule_pressure_index": 10,
            "night_shift_days": 0,
            "cross_operation_count": 0,
            "weather_alert_level": 0,
        },
        "expected": {
            "rule_ids": ["SR-PROJ-001"],
            "risk_level_min": "high",
        },
    }

    evaluation = evaluate_case_backtest(case)

    assert evaluation.passed is True
    assert evaluation.rule_hit is True
    assert evaluation.risk_hit is True
    assert "SR-PROJ-001" in evaluation.predicted_rule_ids


def test_evaluate_case_backtest_fails_when_expected_rule_missing():
    case = {
        "case_id": "BT-UNIT-002",
        "profile_type": "project",
        "input": {
            "hazard_overdue_count": 0,
            "major_hazard_overdue_count": 0,
            "equipment_overdue_count": 0,
            "schedule_pressure_index": 8,
            "night_shift_days": 0,
            "cross_operation_count": 0,
            "weather_alert_level": 0,
        },
        "expected": {
            "rule_ids": ["SR-PROJ-001"],
            "risk_level_min": "high",
        },
    }

    evaluation = evaluate_case_backtest(case)

    assert evaluation.passed is False
    assert evaluation.rule_hit is False
    assert evaluation.risk_hit is False


def test_run_case_backtest_from_db_meets_minimum_hit_rate():
    db = _session()
    seed_accident_cases(db)

    report = run_case_backtest_from_db(db, tenant_id="CSCEC")

    assert report["total_cases"] >= 50
    assert report["coverage"]["mapped_rate"] >= 0.9
    assert report["hit_rate"] >= MIN_DB_HIT_RATE
    assert report["rule_hit_rate"] >= MIN_DB_HIT_RATE
    assert report["risk_level_hit_rate"] >= MIN_DB_HIT_RATE


def test_case_backtest_dataset_exists_and_has_thirty_cases():
    assert DEFAULT_DATASET_PATH.is_file()
    cases = load_case_backtest_cases()
    assert len(cases) == 30


def test_case_backtest_dataset_schema():
    cases = load_case_backtest_cases()
    profile_type_counts = {key: 0 for key in VALID_PROFILE_TYPES}

    for case in cases:
        assert REQUIRED_DATASET_FIELDS.issubset(case.keys())
        assert case["profile_type"] in VALID_PROFILE_TYPES
        profile_type_counts[case["profile_type"]] += 1

        expected = case["expected"]
        assert "risk_level_min" in expected
        assert expected["risk_level_min"] in VALID_RISK_LEVELS
        assert isinstance(expected.get("rule_ids", []), list)

        if case["profile_type"] == "project":
            assert isinstance(case["input"], dict)
            for field in (
                "hazard_overdue_count",
                "major_hazard_overdue_count",
                "equipment_overdue_count",
                "schedule_pressure_index",
            ):
                assert field in case["input"]

    assert profile_type_counts["project"] >= 10
    assert profile_type_counts["worker"] >= 5
    assert profile_type_counts["subcontractor"] >= 3


def test_case_backtest_dataset_meets_hit_rate_gate():
    cases = load_case_backtest_cases()
    report = run_case_backtest(cases)

    if report["failed_cases"]:
        failures = [
            {
                "case_id": item["case_id"],
                "errors": item["errors"],
                "predicted_risk_level": item["predicted_risk_level"],
                "predicted_rule_ids": item["predicted_rule_ids"],
            }
            for item in report["evaluations"]
            if not item["passed"]
        ]
        pytest.fail(
            f"case_backtest hit_rate={report['hit_rate']} below {MIN_DATASET_HIT_RATE}; "
            f"failures={failures}"
        )

    assert report["hit_rate"] >= MIN_DATASET_HIT_RATE
    assert report["rule_hit_rate"] >= MIN_DATASET_HIT_RATE
    assert report["risk_level_hit_rate"] >= MIN_DATASET_HIT_RATE
    assert report["total_cases"] == 30
    assert report["passed_cases"] == 30


def test_build_backtest_case_from_accident_row_uses_case_labels():
    db = _session()
    seed_accident_cases(db)
    row = db.query(AccidentCaseLibrary).filter_by(accident_case_id="AC-MVP-005").one()

    case = build_backtest_case_from_accident_row(row)
    evaluation = evaluate_case_backtest(case)

    assert case["profile_type"] == "project"
    assert "SR-PROJ-001" in case["expected"]["rule_ids"]
    assert evaluation.passed is True


def test_run_case_backtest_report_shape():
    cases = [
        {
            "case_id": "BT-REPORT-001",
            "profile_type": "worker",
            "input": {
                "exam_score": 55,
                "violation_count_30d": 3,
                "special_cert_status": "expired",
                "health_check_status": "valid",
                "entry_days": 90,
            },
            "expected": {
                "rule_ids": ["SR-WORKER-001", "SR-WORKER-005"],
                "risk_level_min": "high",
            },
        }
    ]

    report = run_case_backtest(cases)

    assert report["total_cases"] == 1
    assert report["passed_cases"] == 1
    assert report["hit_rate"] == 1.0
    assert report["evaluations"][0]["case_id"] == "BT-REPORT-001"
