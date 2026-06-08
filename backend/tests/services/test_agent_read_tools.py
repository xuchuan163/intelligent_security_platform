import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import MockUser, ScopeType
from app.infrastructure.database.models import (
    Hazard,
    MetricCatalog,
    ProjectRiskProfile,
    RuleTriggerLog,
)
from app.infrastructure.database.session import Base
from app.services.agents.dag_executor import execute_agent_dag


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def _project_user(project_ids: tuple[str, ...] = ("P002",)) -> MockUser:
    return MockUser(
        user_id="U-PROJECT",
        user_name="Project User",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        role="project_safety_officer",
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=project_ids,
    )


def _route_result(tool_name: str) -> dict:
    return {
        "target_agent": "safety_supervisor",
        "need_human_review": False,
        "blocked_actions": [],
        "planned_steps": [
            {
                "step_id": "step_1",
                "agent_code": "safety_supervisor",
                "action": f"read_{tool_name}",
                "depends_on": [],
                "input_refs": ["context.project_id"],
                "output_key": "tool_summary",
                "requires_human_review": False,
                "will_execute": False,
                "tool_name": tool_name,
            }
        ],
    }


def _execute_tool(db, tool_name: str, context: dict | None = None) -> dict:
    result = execute_agent_dag(
        db,
        route_result=_route_result(tool_name),
        message=f"run {tool_name}",
        context=context or {"project_id": "P002"},
        current_user=_project_user(),
        execution_mode="controlled_execute",
    )
    assert result["dag_status"] == "succeeded"
    step = result["step_results"][0]
    assert step["status"] == "executed"
    assert step["will_execute"] is True
    return step["output_summary"]


def test_profile_read_returns_project_profile_summary():
    engine, db = _session()
    try:
        db.add(
            ProjectRiskProfile(
                project_id="P002",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                calc_date=dt.date(2026, 6, 6),
                total_risk_score=82.5,
                risk_level="critical",
                confidence_level="high",
                risk_tags={"tags": ["major_hazard"]},
            )
        )
        db.commit()

        summary = _execute_tool(db, "profile.read")

        assert summary["row_count"] == 1
        assert summary["fields"] == [
            "profile_type",
            "object_id",
            "project_id",
            "risk_score",
            "risk_level",
            "calculated_at",
            "confidence_level",
        ]
        assert summary["items"][0]["profile_type"] == "project"
        assert summary["items"][0]["object_id"] == "P002"
        assert summary["items"][0]["risk_score"] == 82.5
        assert "strong_rule_flags" not in summary["items"][0]
    finally:
        db.close()
        engine.dispose()


def test_rules_read_triggers_returns_scoped_trigger_summary():
    engine, db = _session()
    try:
        db.add_all(
            [
                RuleTriggerLog(
                    rule_id="SR-PROJ-001",
                    tenant_id="COMPANY-A",
                    company_id="COMPANY-A",
                    org_path="COMPANY-A/P002",
                    object_type="project",
                    object_id="P002",
                    project_id="P002",
                    trigger_condition="major hazard overdue",
                    evidence={"hazard_id": "H-001", "details": "x" * 1000},
                    risk_action="hazard_rectification",
                    severity="urgent",
                ),
                RuleTriggerLog(
                    rule_id="SR-PROJ-999",
                    tenant_id="COMPANY-A",
                    company_id="COMPANY-A",
                    org_path="COMPANY-A/P999",
                    object_type="project",
                    object_id="P999",
                    project_id="P999",
                    trigger_condition="outside scope",
                    evidence={},
                    risk_action="review",
                    severity="low",
                ),
            ]
        )
        db.commit()

        summary = _execute_tool(db, "rules.read_triggers")

        assert summary["row_count"] == 1
        assert summary["items"][0] == {
            "rule_id": "SR-PROJ-001",
            "object_type": "project",
            "object_id": "P002",
            "project_id": "P002",
            "severity": "urgent",
            "risk_action": "hazard_rectification",
        }
    finally:
        db.close()
        engine.dispose()


def test_hazards_read_returns_hazard_summary_without_file_paths():
    engine, db = _session()
    try:
        db.add(
            Hazard(
                hazard_id="H-DAG-001",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                hazard_type="edge_protection",
                hazard_level="major",
                description="Missing edge protection",
                status="open",
                due_date=dt.date(2026, 6, 12),
                is_major=True,
                attachments={"items": [{"file_id": "F-001", "path": "uploads/raw.jpg"}]},
                work_order_id="WO-DAG-001",
            )
        )
        db.commit()

        summary = _execute_tool(db, "hazards.read")

        assert summary["row_count"] == 1
        assert summary["items"][0] == {
            "hazard_id": "H-DAG-001",
            "project_id": "P002",
            "hazard_type": "edge_protection",
            "hazard_level": "major",
            "status": "open",
            "due_date": "2026-06-12",
            "is_major": True,
            "work_order_id": "WO-DAG-001",
            "attachment_count": 1,
        }
        assert "path" not in summary["items"][0]
    finally:
        db.close()
        engine.dispose()


def test_metrics_read_catalog_returns_metadata_without_sql_execution():
    engine, db = _session()
    try:
        db.add(
            MetricCatalog(
                company_id="COMPANY-A",
                project_id=None,
                metric_code="PROJECT_RISK_SCORE",
                metric_name="Project Risk Score",
                business_definition="Composite project risk score.",
                calculation_formula="weighted_sum",
                dimensions=["project"],
                source_tables=["project_risk_profile"],
                source_fields=["total_risk_score"],
                aliases=["risk score"],
                status="enabled",
            )
        )
        db.commit()

        summary = _execute_tool(db, "metrics.read_catalog", context={})

        assert summary["row_count"] == 1
        assert summary["items"][0] == {
            "metric_code": "PROJECT_RISK_SCORE",
            "metric_name": "Project Risk Score",
            "business_definition": "Composite project risk score.",
            "calculation_formula": "weighted_sum",
            "source_tables": ["project_risk_profile"],
            "source_fields": ["total_risk_score"],
            "aliases": ["risk score"],
        }
        assert "sql" not in summary
    finally:
        db.close()
        engine.dispose()
