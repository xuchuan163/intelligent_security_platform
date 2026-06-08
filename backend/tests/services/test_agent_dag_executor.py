from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import MockUser, ScopeType
from app.infrastructure.database.models import SafetyWorkOrder
from app.infrastructure.database.session import Base
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


def test_agent_dag_audit_tables_are_declared_in_orm_metadata():
    from app.infrastructure.database.models import AgentDagRun, AgentDagStepRun

    assert AgentDagRun.__tablename__ == "agent_dag_run"
    assert AgentDagStepRun.__tablename__ == "agent_dag_step_run"
    run_columns = {column.name for column in Base.metadata.tables["agent_dag_run"].columns}
    step_columns = {column.name for column in Base.metadata.tables["agent_dag_step_run"].columns}

    assert {"run_id", "company_id", "project_id", "scope_type", "status"} <= run_columns
    assert {"step_run_id", "run_id", "step_id", "tool_name", "status"} <= step_columns


def test_dry_run_persists_audit_records_without_executing_tools():
    from app.infrastructure.database.models import AgentDagRun, AgentDagStepRun
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        message = "List open work orders for P002 and explain the safety risk."
        context = {"project_id": "P002"}
        route_result = route_agent_message(db, message, context=context, execution_mode="plan_only")

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message=message,
            context=context,
            current_user=_project_user(),
            execution_mode="dry_run",
        )

        assert result["dag_status"] == "dry_run_passed"
        assert result["dag_execution_allowed"] is False
        assert result["run_id"].startswith("AGDAG-")
        assert result["step_results"]
        assert all(step["will_execute"] is False for step in result["step_results"])
        assert all(step["status"] == "dry_run_passed" for step in result["step_results"])

        run = db.query(AgentDagRun).filter_by(run_id=result["run_id"]).one()
        steps = db.query(AgentDagStepRun).filter_by(run_id=result["run_id"]).all()
        assert run.status == "dry_run_passed"
        assert run.project_id == "P002"
        assert len(steps) == len(result["step_results"])
    finally:
        db.close()
        engine.dispose()


def test_dry_run_blocks_unauthorized_project_context():
    from app.infrastructure.database.models import AgentDagRun
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        message = "List open work orders for P999."
        context = {"project_id": "P999"}
        route_result = route_agent_message(db, message, context=context, execution_mode="plan_only")

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message=message,
            context=context,
            current_user=_project_user(project_ids=("P002",)),
            execution_mode="dry_run",
        )

        assert result["dag_status"] == "blocked"
        assert result["dag_execution_allowed"] is False
        assert "project" in result["blocked_reason"]
        run = db.query(AgentDagRun).filter_by(run_id=result["run_id"]).one()
        assert run.status == "blocked"
        assert "project" in run.blocked_reason
    finally:
        db.close()
        engine.dispose()


def test_dry_run_blocks_restricted_action_language():
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        message = "stop work and remove subcontractor because this hazard is critical"
        context = {"project_id": "P002"}
        route_result = route_agent_message(db, message, context=context, execution_mode="plan_only")

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message=message,
            context=context,
            current_user=_project_user(),
            execution_mode="dry_run",
        )

        assert result["dag_status"] == "blocked"
        assert result["need_human_review"] is True
        assert result["blocked_reason"] == "restricted_action"
        assert any(step["status"] == "blocked" for step in result["step_results"])
    finally:
        db.close()
        engine.dispose()


def test_controlled_execute_runs_read_only_tool_and_returns_summary():
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        db.add(
            SafetyWorkOrder(
                work_order_id="WO-DAG-001",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                work_order_type="hazard_rectification",
                project_id="P002",
                title="Open hazard",
                status="pending_confirm",
                priority="high",
            )
        )
        db.commit()
        route_result = {
            "target_agent": "work_order_coordinator",
            "need_human_review": False,
            "blocked_actions": [],
            "planned_steps": [
                {
                    "step_id": "step_1",
                    "agent_code": "safety_supervisor",
                    "action": "classify_intent_and_route",
                    "depends_on": [],
                    "input_refs": ["message"],
                    "output_key": "route",
                    "requires_human_review": False,
                    "will_execute": False,
                    "tool_name": None,
                },
                {
                    "step_id": "step_2",
                    "agent_code": "work_order_coordinator",
                    "action": "inspect_work_order_state",
                    "depends_on": ["step_1"],
                    "input_refs": ["context.project_id"],
                    "output_key": "work_order_state",
                    "requires_human_review": False,
                    "will_execute": False,
                    "tool_name": "work_orders.read",
                },
            ],
        }

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message="List open work orders for P002",
            context={"project_id": "P002"},
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        assert result["dag_status"] == "succeeded"
        assert result["dag_execution_allowed"] is True
        read_step = result["step_results"][1]
        assert read_step["status"] == "executed"
        assert read_step["will_execute"] is True
        assert read_step["output_summary"] == {
            "row_count": 1,
            "fields": ["work_order_id", "status", "priority"],
        }
    finally:
        db.close()
        engine.dispose()


def test_controlled_execute_converts_write_tool_to_approval_required():
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        route_result = {
            "target_agent": "work_order_coordinator",
            "need_human_review": False,
            "blocked_actions": [],
            "planned_steps": [
                {
                    "step_id": "step_1",
                    "agent_code": "work_order_coordinator",
                    "action": "transition_work_order",
                    "depends_on": [],
                    "input_refs": ["context.work_order_id"],
                    "output_key": "transition",
                    "requires_human_review": False,
                    "will_execute": False,
                    "tool_name": "work_orders.transition",
                }
            ],
        }

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message="Dispatch WO-DAG-001",
            context={"project_id": "P002", "work_order_id": "WO-DAG-001"},
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        assert result["dag_status"] == "approval_required"
        assert result["dag_execution_allowed"] is False
        assert result["step_results"][0]["status"] == "approval_required"
        assert result["step_results"][0]["will_execute"] is False
    finally:
        db.close()
        engine.dispose()


def test_controlled_execute_skips_steps_depending_on_blocked_step():
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        route_result = {
            "target_agent": "work_order_coordinator",
            "need_human_review": False,
            "blocked_actions": [],
            "planned_steps": [
                {
                    "step_id": "step_1",
                    "agent_code": "work_order_coordinator",
                    "action": "call_unknown_tool",
                    "depends_on": [],
                    "input_refs": [],
                    "output_key": "unknown",
                    "requires_human_review": False,
                    "will_execute": False,
                    "tool_name": "unknown.tool",
                },
                {
                    "step_id": "step_2",
                    "agent_code": "work_order_coordinator",
                    "action": "inspect_work_order_state",
                    "depends_on": ["step_1"],
                    "input_refs": ["context.project_id"],
                    "output_key": "work_order_state",
                    "requires_human_review": False,
                    "will_execute": False,
                    "tool_name": "work_orders.read",
                },
            ],
        }

        result = execute_agent_dag(
            db,
            route_result=route_result,
            message="Read work order after unknown step",
            context={"project_id": "P002"},
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        assert result["dag_status"] == "blocked"
        assert result["step_results"][0]["status"] == "blocked"
        assert result["step_results"][1]["status"] == "skipped"
        assert result["step_results"][1]["will_execute"] is False
    finally:
        db.close()
        engine.dispose()
