import datetime as dt

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import MockUser, ScopeType
from app.infrastructure.database.models import AgentApprovalRequest, Project, ProjectUser, SafetyWorkOrder
from app.infrastructure.database.session import Base, get_db
from app.main import app
from app.services.agents.prompt_registry import sync_agent_prompt_versions


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


def _user(role: str, user_id: str, project_ids: tuple[str, ...] = ("P002",)) -> MockUser:
    return MockUser(
        user_id=user_id,
        user_name=user_id,
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        role=role,
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=project_ids,
    )


def _seed_project_and_order(db, *, status: str = "pending_confirm") -> None:
    db.add(
        Project(
            project_id="P002",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P002",
            project_name="Wuhan Center",
            status="active",
        )
    )
    db.add_all(
        [
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-DIR-01",
                user_name="Safety Director",
                role_code="safety_director",
            ),
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-GC-01",
                user_name="GC Safety",
                role_code="gc_safety_officer",
            ),
        ]
    )
    db.add(
        SafetyWorkOrder(
            work_order_id="WO-EXEC-001",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P002",
            work_order_type="hazard_rectification",
            source_type="hazard",
            source_id="H-EXEC-001",
            project_id="P002",
            title="Execution approval hazard",
            status=status,
            priority="high",
        )
    )
    db.commit()


def _approval(db, *, status: str = "approved", tool: str = "work_orders.transition") -> AgentApprovalRequest:
    approval = AgentApprovalRequest(
        approval_id=f"AGAPR-EXEC-{status.upper()}-{tool.replace('.', '-').upper()}",
        run_id=f"AGDAG-EXEC-{status}",
        step_run_id=f"AGSTEP-EXEC-{status}",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        project_id="P002",
        scope_type="project",
        request_user_id="U-AGENT",
        requested_tool=tool,
        requested_action="request_work_order_transition_approval",
        target_type="work_order",
        target_id="WO-EXEC-001",
        payload_summary="Execute work-order transition",
        payload_json={
            "project_id": "P002",
            "work_order_id": "WO-EXEC-001",
            "action": "confirm",
            "assignee_user_id": "U-SUB-S003",
            "due_time": "2026-06-10T18:00:00",
            "comment": "Approved by human.",
        },
        risk_level="medium",
        reason="write-side tool work_orders.transition requires human approval",
        evidence_refs=[],
        status=status,
    )
    db.add(approval)
    db.commit()
    return approval


def test_agent_approval_request_execution_columns_are_declared():
    table = Base.metadata.tables["agent_approval_request"]
    columns = {column.name for column in table.columns}

    assert {"executor_user_id", "executed_at", "execution_result", "execution_error"} <= columns


def test_execute_approved_work_order_transition_updates_order_and_audit_record():
    from app.services.agents.approval_queue import execute_approved_request

    engine, db = _session()
    try:
        _seed_project_and_order(db)
        approval = _approval(db)

        result = execute_approved_request(
            db,
            approval_id=approval.approval_id,
            current_user=_user("safety_director", "U-DIR-01"),
        )

        order = db.query(SafetyWorkOrder).filter_by(work_order_id="WO-EXEC-001").one()
        stored = db.query(AgentApprovalRequest).filter_by(approval_id=approval.approval_id).one()

        assert result["status"] == "executed"
        assert result["executor_user_id"] == "U-DIR-01"
        assert result["execution_result"]["new_status"] == "dispatched"
        assert order.status == "dispatched"
        assert order.responsible_user_id == "U-SUB-S003"
        assert stored.status == "executed"
        assert stored.executor_user_id == "U-DIR-01"
        assert stored.executed_at is not None
        assert stored.execution_result["new_status"] == "dispatched"
        assert stored.execution_error is None
    finally:
        db.close()
        engine.dispose()


@pytest.mark.parametrize("status", ["pending", "rejected", "executed", "execution_failed"])
def test_execute_requires_approved_status(status):
    from app.services.agents.approval_queue import execute_approved_request

    engine, db = _session()
    try:
        _seed_project_and_order(db)
        approval = _approval(db, status=status)

        with pytest.raises(ValueError, match="Only approved approval requests can be executed"):
            execute_approved_request(
                db,
                approval_id=approval.approval_id,
                current_user=_user("safety_director", "U-DIR-01"),
            )

        stored = db.query(AgentApprovalRequest).filter_by(approval_id=approval.approval_id).one()
        assert stored.status == status
    finally:
        db.close()
        engine.dispose()


def test_execute_rechecks_workflow_role_and_records_execution_failed():
    from app.services.agents.approval_queue import execute_approved_request

    engine, db = _session()
    try:
        _seed_project_and_order(db)
        approval = _approval(db)

        with pytest.raises(PermissionError, match="Action is not allowed"):
            execute_approved_request(
                db,
                approval_id=approval.approval_id,
                current_user=_user("gc_safety_officer", "U-GC-01"),
            )

        order = db.query(SafetyWorkOrder).filter_by(work_order_id="WO-EXEC-001").one()
        stored = db.query(AgentApprovalRequest).filter_by(approval_id=approval.approval_id).one()
        assert order.status == "pending_confirm"
        assert stored.status == "execution_failed"
        assert stored.executor_user_id == "U-GC-01"
        assert "Action is not allowed" in stored.execution_error
    finally:
        db.close()
        engine.dispose()


def test_execute_rejects_non_work_order_transition_tool():
    from app.services.agents.approval_queue import execute_approved_request

    engine, db = _session()
    try:
        _seed_project_and_order(db)
        approval = _approval(db, tool="hazards.create")

        with pytest.raises(PermissionError, match="Only approved work order tools"):
            execute_approved_request(
                db,
                approval_id=approval.approval_id,
                current_user=_user("safety_director", "U-DIR-01"),
            )

        stored = db.query(AgentApprovalRequest).filter_by(approval_id=approval.approval_id).one()
        assert stored.status == "execution_failed"
        assert "Only approved work order tools" in stored.execution_error
    finally:
        db.close()
        engine.dispose()


def test_execute_api_runs_approved_request_with_current_user_identity():
    engine, db = _session()
    try:
        _seed_project_and_order(db)
        approval = _approval(db)

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        response = client.post(
            f"/api/v1/agent/approvals/{approval.approval_id}/execute",
            headers={
                "X-Tenant-Id": "COMPANY-A",
                "X-Company-Id": "COMPANY-A",
                "X-Mock-User-Id": "U-DIR-01",
                "X-Role": "safety_director",
                "X-Scope-Type": "project",
                "X-Authorized-Project-Ids": "P002",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "executed"
        assert data["executor_user_id"] == "U-DIR-01"
        assert data["execution_result"]["new_status"] == "dispatched"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_agent_controlled_execute_still_does_not_auto_execute_work_order():
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        _seed_project_and_order(db)
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
            message="Dispatch WO-EXEC-001",
            context={
                "project_id": "P002",
                "work_order_id": "WO-EXEC-001",
                "action": "confirm",
                "assignee_user_id": "U-SUB-S003",
                "due_time": "2026-06-10T18:00:00",
            },
            current_user=_user("safety_director", "U-DIR-01"),
            execution_mode="controlled_execute",
        )

        order = db.query(SafetyWorkOrder).filter_by(work_order_id="WO-EXEC-001").one()
        approval = db.query(AgentApprovalRequest).filter_by(approval_id=result["step_results"][0]["approval_id"]).one()
        assert result["dag_status"] == "approval_required"
        assert approval.status == "pending"
        assert order.status == "pending_confirm"
    finally:
        db.close()
        engine.dispose()
