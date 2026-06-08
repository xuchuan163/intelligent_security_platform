import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import MockUser, ScopeType
from app.infrastructure.database.models import Hazard, RuleTriggerLog, SafetyWorkOrder
from app.infrastructure.database.session import Base
from app.services.agents.dag_executor import execute_agent_dag
from app.services.agents.hazard_rectification import (
    build_evidence_refs,
    draft_rectification_suggestion,
    load_hazard_evidence_bundle,
)
from app.services.agents.prompt_registry import sync_agent_prompt_versions
from app.services.agents.router import route_agent_message


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)
    return engine, db


def _project_user() -> MockUser:
    return MockUser(
        user_id="U-HAZARD",
        user_name="Hazard Advisor",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P001",
        role="project_safety_officer",
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P001",),
    )


def _seed_hazard(db, *, work_order_id: str | None = "WO-HAZ-001") -> Hazard:
    if work_order_id:
        db.add(
            SafetyWorkOrder(
                work_order_id=work_order_id,
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P001",
                work_order_type="hazard_rectification",
                project_id="P001",
                title="临边防护缺失",
                status="pending_confirm",
                priority="high",
            )
        )
    hazard = Hazard(
        hazard_id="H-ADV-001",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P001",
        project_id="P001",
        hazard_type="edge_protection",
        hazard_level="major",
        description="临边防护缺失",
        status="open",
        due_date=dt.date(2026, 6, 12),
        is_major=True,
        work_order_id=work_order_id,
    )
    db.add(hazard)
    db.add(
        RuleTriggerLog(
            rule_id="SR-PROJ-001",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P001",
            object_type="project",
            object_id="P001",
            project_id="P001",
            trigger_condition="major hazard overdue",
            evidence={},
            risk_action="hazard_rectification",
            severity="urgent",
        )
    )
    db.commit()
    return hazard


def test_load_hazard_evidence_bundle_collects_hazard_work_order_and_rules():
    engine, db = _session()
    try:
        _seed_hazard(db)
        bundle = load_hazard_evidence_bundle(
            db,
            hazard_id="H-ADV-001",
            project_id="P001",
            current_user=_project_user(),
        )
        assert bundle["hazard"]["hazard_id"] == "H-ADV-001"
        assert bundle["work_order"]["work_order_id"] == "WO-HAZ-001"
        assert bundle["rule_triggers"][0]["rule_id"] == "SR-PROJ-001"
    finally:
        db.close()
        engine.dispose()


def test_draft_rectification_suggestion_uses_scaffold_measures_for_chinese_hazard_type():
    engine, db = _session()
    try:
        hazard = Hazard(
            hazard_id="H-SCAFFOLD-001",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P001",
            project_id="P001",
            hazard_type="脚手架",
            hazard_level="major",
            description="外架连墙件不足",
            status="open",
            due_date=dt.date(2026, 6, 12),
            is_major=True,
        )
        db.add(hazard)
        db.commit()

        result = draft_rectification_suggestion(
            db,
            message="脚手架隐患如何整改",
            context={"hazard_id": "H-SCAFFOLD-001", "project_id": "P001"},
            current_user=_project_user(),
            llm_client=None,
        )

        assert result["status"] == "generated"
        assert any("连墙件" in item for item in result["rectification_suggestions"])
    finally:
        db.close()
        engine.dispose()


def test_draft_rectification_suggestion_returns_evidence_backed_plan():
    engine, db = _session()
    try:
        _seed_hazard(db)
        result = draft_rectification_suggestion(
            db,
            message="这个临边防护隐患应该怎么整改",
            context={"hazard_id": "H-ADV-001", "project_id": "P001"},
            current_user=_project_user(),
            llm_client=None,
        )
        assert result["status"] == "generated"
        assert result["hazard_id"] == "H-ADV-001"
        assert result["rectification_suggestions"]
        assert result["review_checkpoints"]
        evidence = build_evidence_refs(
            load_hazard_evidence_bundle(
                db,
                hazard_id="H-ADV-001",
                project_id="P001",
                current_user=_project_user(),
            )
        )
        assert any(item["ref_type"] == "hazard" for item in result["evidence"])
        assert any(item["ref_type"] == "work_order" for item in evidence)
        assert result["need_human_review"] is True
    finally:
        db.close()
        engine.dispose()


class _FailingQwenClient:
    def chat(self, messages, temperature=0.0):
        raise AssertionError("LLM should not be invoked in demo_mode")


def test_controlled_execute_demo_mode_skips_llm_enhancement(monkeypatch):
    engine, db = _session()
    try:
        monkeypatch.setattr("app.services.agents.dag_executor.qwen", _FailingQwenClient())
        _seed_hazard(db, work_order_id=None)
        message = "这个脚手架隐患应该怎么整改"
        context = {"hazard_id": "H-ADV-001", "project_id": "P001", "demo_mode": True}
        route_result = route_agent_message(db, message, context=context, execution_mode="plan_only")

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message=message,
            context=context,
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        draft_steps = [
            step
            for step in result["step_results"]
            if step["action"] == "draft_rectification_suggestion"
        ]
        assert result["dag_status"] == "succeeded"
        assert draft_steps[0]["status"] == "executed"
        assert draft_steps[0]["output_summary"]["status"] == "generated"
        assert draft_steps[0]["output_summary"]["llm_enhanced"] is False
    finally:
        db.close()
        engine.dispose()


def test_controlled_execute_runs_hazard_rectification_draft_step():
    engine, db = _session()
    try:
        _seed_hazard(db, work_order_id=None)
        message = "这个临边防护隐患应该怎么整改"
        context = {"hazard_id": "H-ADV-001", "project_id": "P001"}
        route_result = route_agent_message(db, message, context=context, execution_mode="plan_only")

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message=message,
            context=context,
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        draft_steps = [
            step
            for step in result["step_results"]
            if step["action"] == "draft_rectification_suggestion"
        ]
        assert draft_steps
        assert draft_steps[0]["status"] == "executed"
        assert draft_steps[0]["output_summary"]["hazard_id"] == "H-ADV-001"
        assert draft_steps[0]["output_summary"]["evidence"]
    finally:
        db.close()
        engine.dispose()


def test_controlled_execute_creates_work_order_create_approval_when_requested():
    engine, db = _session()
    try:
        _seed_hazard(db, work_order_id=None)
        message = "请为这个隐患生成整改工单"
        context = {
            "hazard_id": "H-ADV-001",
            "project_id": "P001",
            "propose_work_order": True,
        }
        route_result = route_agent_message(db, message, context=context, execution_mode="plan_only")

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message=message,
            context=context,
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        assert result["dag_status"] == "approval_required"
        create_steps = [step for step in result["step_results"] if step["tool_name"] == "work_orders.create"]
        assert create_steps
        assert create_steps[0]["status"] == "approval_required"
        assert create_steps[0]["approval_id"]
    finally:
        db.close()
        engine.dispose()


def test_execute_approved_work_order_create_creates_rectification_order():
    from app.services.agents.approval_queue import (
        create_approval_request_for_step,
        decide_approval_request,
        execute_approved_request,
    )

    engine, db = _session()
    try:
        _seed_hazard(db, work_order_id=None)
        user = _project_user()
        approval = create_approval_request_for_step(
            db,
            run_id="AGDAG-TEST-001",
            step_run_id="AGSTEP-TEST-001",
            step={
                "action": "propose_rectification_work_order",
                "agent_code": "hazard_rectification_advisor",
            },
            tool_name="work_orders.create",
            context={
                "project_id": "P001",
                "hazard_id": "H-ADV-001",
                "title": "临边防护整改",
                "description": "补设防护栏杆",
                "work_order_type": "hazard_rectification",
                "source_type": "hazard",
                "source_id": "H-ADV-001",
                "priority": "high",
            },
            current_user=user,
            reason="write-side tool work_orders.create requires human approval",
        )
        db.commit()
        decide_approval_request(
            db,
            approval_id=approval.approval_id,
            current_user=user,
            decision="approved",
            comment="同意开单",
        )
        result = execute_approved_request(
            db,
            approval_id=approval.approval_id,
            current_user=user,
        )
        assert result is not None
        assert result["status"] == "executed"
        assert result["execution_result"]["work_order_id"]
        assert result["execution_result"]["status"] == "pending_confirm"
    finally:
        db.close()
        engine.dispose()


def test_hazard_plan_includes_knowledge_search_step():
    engine, db = _session()
    try:
        route_result = route_agent_message(
            db,
            "这个临边防护隐患应该怎么整改",
            context={"hazard_id": "H-ADV-001", "project_id": "P001"},
            execution_mode="plan_only",
        )

        tool_names = [step.get("tool_name") for step in route_result["planned_steps"]]
        assert "hazards.read" in tool_names
        assert "knowledge.search" in tool_names
    finally:
        db.close()
        engine.dispose()
