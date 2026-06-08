from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.security import MockUser, ScopeType
from app.infrastructure.database.models import SafetyWorkOrder
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


def _write_route(tool_name: str = "work_orders.transition") -> dict:
    return {
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
                "tool_name": tool_name,
            }
        ],
    }


def test_agent_approval_request_table_is_declared_in_orm_metadata():
    table = Base.metadata.tables["agent_approval_request"]
    columns = {column.name for column in table.columns}

    assert {
        "approval_id",
        "run_id",
        "step_run_id",
        "tenant_id",
        "company_id",
        "project_id",
        "scope_type",
        "request_user_id",
        "requested_tool",
        "requested_action",
        "target_type",
        "target_id",
        "payload_summary",
        "payload_json",
        "risk_level",
        "reason",
        "evidence_refs",
        "status",
        "approver_user_id",
        "approval_comment",
        "approved_at",
        "rejected_at",
        "expires_at",
    } <= columns


def test_controlled_execute_write_tool_creates_pending_approval_without_changing_work_order():
    from app.infrastructure.database.models import AgentApprovalRequest
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        db.add(
            SafetyWorkOrder(
                work_order_id="WO-APPROVAL-001",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                work_order_type="hazard_rectification",
                project_id="P002",
                title="Pending hazard",
                status="pending_confirm",
                priority="high",
            )
        )
        db.commit()

        result = execute_agent_dag(
            db,
            route_result=_write_route(),
            message="Dispatch WO-APPROVAL-001",
            context={"project_id": "P002", "work_order_id": "WO-APPROVAL-001", "action": "confirm"},
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        approval_id = result["step_results"][0]["approval_id"]
        approval = db.query(AgentApprovalRequest).filter_by(approval_id=approval_id).one()
        order = db.query(SafetyWorkOrder).filter_by(work_order_id="WO-APPROVAL-001").one()

        assert result["dag_status"] == "approval_required"
        assert result["dag_execution_allowed"] is False
        assert result["step_results"][0]["status"] == "approval_required"
        assert result["step_results"][0]["will_execute"] is False
        assert result["step_results"][0]["output_summary"]["approval_id"] == approval_id
        assert approval.status == "pending"
        assert approval.requested_tool == "work_orders.transition"
        assert approval.target_type == "work_order"
        assert approval.target_id == "WO-APPROVAL-001"
        assert order.status == "pending_confirm"
    finally:
        db.close()
        engine.dispose()


def test_dry_run_write_tool_does_not_create_approval():
    from app.infrastructure.database.models import AgentApprovalRequest
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        result = execute_agent_dag(
            db,
            route_result=_write_route(),
            message="Dispatch WO-APPROVAL-DRY",
            context={"project_id": "P002", "work_order_id": "WO-APPROVAL-DRY"},
            current_user=_project_user(),
            execution_mode="dry_run",
        )

        assert result["dag_status"] == "approval_required"
        assert db.query(AgentApprovalRequest).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_restricted_tool_does_not_create_approval_request():
    from app.infrastructure.database.models import AgentApprovalRequest
    from app.services.agents.dag_executor import execute_agent_dag

    engine, db = _session()
    try:
        result = execute_agent_dag(
            db,
            route_result=_write_route("stop_work.issue"),
            message="Issue stop work",
            context={"project_id": "P002"},
            current_user=_project_user(),
            execution_mode="controlled_execute",
        )

        assert result["dag_status"] == "blocked"
        assert result["step_results"][0]["status"] == "blocked"
        assert db.query(AgentApprovalRequest).count() == 0
    finally:
        db.close()
        engine.dispose()


def test_approval_api_lists_scoped_pending_items_and_approve_reject_are_state_only():
    from app.infrastructure.database.models import AgentApprovalRequest

    engine, db = _session()
    try:
        db.add_all(
            [
                AgentApprovalRequest(
                    approval_id="AGAPR-P002",
                    run_id="AGDAG-P002",
                    step_run_id="AGSTEP-P002",
                    tenant_id="COMPANY-A",
                    company_id="COMPANY-A",
                    project_id="P002",
                    scope_type="project",
                    request_user_id="U-AGENT",
                    requested_tool="work_orders.transition",
                    requested_action="transition_work_order",
                    target_type="work_order",
                    target_id="WO-APPROVAL-API",
                    payload_summary="Approve work-order transition",
                    payload_json={"work_order_id": "WO-APPROVAL-API", "action": "confirm"},
                    risk_level="medium",
                    reason="write-side tool work_orders.transition requires human approval",
                    evidence_refs=[],
                    status="pending",
                ),
                AgentApprovalRequest(
                    approval_id="AGAPR-P999",
                    run_id="AGDAG-P999",
                    step_run_id="AGSTEP-P999",
                    tenant_id="COMPANY-A",
                    company_id="COMPANY-A",
                    project_id="P999",
                    scope_type="project",
                    request_user_id="U-AGENT",
                    requested_tool="work_orders.transition",
                    requested_action="transition_work_order",
                    target_type="work_order",
                    target_id="WO-HIDDEN",
                    payload_summary="Hidden transition",
                    payload_json={"work_order_id": "WO-HIDDEN"},
                    risk_level="medium",
                    reason="write-side tool work_orders.transition requires human approval",
                    evidence_refs=[],
                    status="pending",
                ),
            ]
        )
        db.add(
            SafetyWorkOrder(
                work_order_id="WO-APPROVAL-API",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                work_order_type="hazard_rectification",
                project_id="P002",
                title="API approval hazard",
                status="pending_confirm",
                priority="high",
            )
        )
        db.commit()

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        headers = {
            "X-Tenant-Id": "COMPANY-A",
            "X-Company-Id": "COMPANY-A",
            "X-Mock-User-Id": "U-APPROVER",
            "X-Scope-Type": "project",
            "X-Authorized-Project-Ids": "P002",
        }

        response = client.get("/api/v1/agent/approvals", headers=headers)
        assert response.status_code == 200
        items = response.json()["data"]["items"]
        assert [item["approval_id"] for item in items] == ["AGAPR-P002"]

        approve_response = client.post(
            "/api/v1/agent/approvals/AGAPR-P002/approve",
            json={"comment": "人工确认，暂不执行"},
            headers=headers,
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["data"]["status"] == "approved"

        order = db.query(SafetyWorkOrder).filter_by(work_order_id="WO-APPROVAL-API").one()
        assert order.status == "pending_confirm"

        reject_response = client.post(
            "/api/v1/agent/approvals/AGAPR-P999/reject",
            json={"comment": "越权项目不可处理"},
            headers=headers,
        )
        assert reject_response.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_agent_ask_controlled_execute_returns_approval_id_for_work_order_write_request():
    from app.infrastructure.database.models import AgentApprovalRequest

    engine, db = _session()
    try:
        db.add(
            SafetyWorkOrder(
                work_order_id="WO-APPROVAL-ASK",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                work_order_type="hazard_rectification",
                project_id="P002",
                title="Ask approval hazard",
                status="pending_confirm",
                priority="high",
            )
        )
        db.commit()

        def override_get_db():
            try:
                yield db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/ask",
            json={
                "message": "Dispatch work order WO-APPROVAL-ASK",
                "execution_mode": "controlled_execute",
                "context": {
                    "project_id": "P002",
                    "work_order_id": "WO-APPROVAL-ASK",
                    "action": "confirm",
                },
            },
            headers={
                "X-Tenant-Id": "COMPANY-A",
                "X-Company-Id": "COMPANY-A",
                "X-Mock-User-Id": "U-AGENT",
                "X-Scope-Type": "project",
                "X-Authorized-Project-Ids": "P002",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        write_steps = [step for step in data["step_results"] if step["tool_name"] == "work_orders.transition"]
        assert write_steps
        assert write_steps[0]["status"] == "approval_required"
        assert write_steps[0]["approval_id"].startswith("AGAPR-")
        assert db.query(AgentApprovalRequest).filter_by(approval_id=write_steps[0]["approval_id"]).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
