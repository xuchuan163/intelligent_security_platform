from app.services.rules.engine import RuleEngine


def test_rule_engine_loads_rules_from_yaml_config():
    engine = RuleEngine.from_config()

    rule_ids = {rule.rule_id for rule in engine.rules}

    assert {"SR-PROJ-001", "SR-PROJ-004", "SR-WORKER-001"} <= rule_ids


def test_rule_engine_loads_at_least_10_strong_rules():
    engine = RuleEngine.from_config()

    rule_ids = {rule.rule_id for rule in engine.rules}

    assert len(engine.rules) >= 10
    assert {
        "SR-PROJ-003",
        "SR-SUB-001",
        "SR-SUB-002",
        "SR-SUB-004",
    } <= rule_ids


def test_rule_engine_evaluates_project_rules_with_evidence_and_bonus():
    engine = RuleEngine.from_config()

    triggered = engine.evaluate(
        "project",
        {
            "major_hazard_overdue_count": 1,
            "equipment_overdue_count": 2,
            "schedule_pressure_index": 10,
        },
    )

    assert [item.rule_id for item in triggered] == ["SR-PROJ-001", "SR-PROJ-004"]
    assert sum(item.risk_bonus for item in triggered) == 45
    assert triggered[0].evidence == {
        "field": "major_hazard_overdue_count",
        "operator": ">",
        "expected": 0,
        "actual": 1,
    }


def test_rule_engine_evaluates_worker_certificate_rule():
    engine = RuleEngine.from_config()

    triggered = engine.evaluate(
        "worker",
        {
            "special_cert_status": "expired",
            "violation_count_30d": 0,
            "health_check_status": "valid",
        },
    )

    assert [item.rule_id for item in triggered] == ["SR-WORKER-001"]
    assert triggered[0].risk_tag == "特种作业证异常"


def test_rule_engine_evaluates_subcontractor_rules():
    engine = RuleEngine.from_config()

    triggered = engine.evaluate(
        "subcontractor",
        {
            "major_hazard_overdue_count": 1,
            "safety_license_status": "expired",
            "accident_history_count": 1,
        },
    )

    assert [item.rule_id for item in triggered] == ["SR-SUB-004", "SR-SUB-001", "SR-SUB-002"]
    assert sum(item.risk_bonus for item in triggered) == 65
