import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.infrastructure.database.session import Base, get_db
from app.infrastructure.database.models import Hazard, MetricCatalog, ProjectRiskProfile, RuleTriggerLog, SafetyWorkOrder
from app.main import app
from app.services.agents.prompt_registry import sync_agent_prompt_versions
from app.services.agents import router as agent_router


class FakeQwenClient:
    def chat(self, messages, temperature=0.0):
        return {
            "available": True,
            "message": "ok",
            "content": '{"route_explanation":"api preview","need_human_review":false}',
        }


def test_agent_ask_returns_route_only_preview():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/ask",
            json={"message": "查询项目风险排名", "context": {"project_id": "P001"}},
            headers={
                "X-Tenant-Id": "COMPANY-A",
                "X-Company-Id": "COMPANY-A",
                "X-Mock-User-Id": "U-AGENT",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SUCCESS"
        data = body["data"]
        assert data["target_agent"] == "nl2sql_analyst"
        assert data["intent"] == "nl2sql"
        assert data["execution_mode"] == "route_only"
        assert data["prompt_version"] == "v1.0"
        assert data["need_human_review"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_agent_ask_execute_preview_returns_llm_preview(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)
    monkeypatch.setattr(agent_router, "qwen", FakeQwenClient())

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/ask",
            json={
                "message": "查询项目风险排名",
                "execution_mode": "execute_preview",
                "context": {"project_id": "P001"},
            },
            headers={
                "X-Tenant-Id": "COMPANY-A",
                "X-Company-Id": "COMPANY-A",
                "X-Mock-User-Id": "U-AGENT",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["execution_mode"] == "execute_preview"
        assert data["target_agent"] == "nl2sql_analyst"
        assert data["preview_status"] == "generated"
        assert data["llm_preview"]["route_explanation"] == "api preview"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_agent_ask_plan_only_returns_planned_steps():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/ask",
            json={
                "message": "sql list top 10 high risk projects",
                "execution_mode": "plan_only",
                "context": {"project_id": "P001"},
            },
            headers={
                "X-Tenant-Id": "COMPANY-A",
                "X-Company-Id": "COMPANY-A",
                "X-Mock-User-Id": "U-AGENT",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SUCCESS"
        data = body["data"]
        assert data["execution_mode"] == "plan_only"
        assert data["dag_status"] == "planned"
        assert data["dag_execution_allowed"] is False
        assert data["planned_steps"]
        assert all(step["will_execute"] is False for step in data["planned_steps"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_agent_ask_dry_run_returns_audited_step_results():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/ask",
            json={
                "message": "List open work orders for P001",
                "execution_mode": "dry_run",
                "context": {"project_id": "P001"},
            },
            headers={
                "X-Tenant-Id": "COMPANY-A",
                "X-Company-Id": "COMPANY-A",
                "X-Mock-User-Id": "U-AGENT",
                "X-Scope-Type": "project",
                "X-Authorized-Project-Ids": "P001",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["execution_mode"] == "dry_run"
        assert data["dag_status"] == "dry_run_passed"
        assert data["dag_execution_allowed"] is False
        assert data["run_id"].startswith("AGDAG-")
        assert data["step_results"]
        assert all(step["will_execute"] is False for step in data["step_results"])
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_agent_ask_controlled_execute_runs_work_order_read_tool():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)
    db.add(
        SafetyWorkOrder(
            work_order_id="WO-API-DAG-001",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P001",
            work_order_type="hazard_rectification",
            project_id="P001",
            title="Open hazard",
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
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/ask",
            json={
                "message": "Check open work order status for P001",
                "execution_mode": "controlled_execute",
                "context": {"project_id": "P001"},
            },
            headers={
                "X-Tenant-Id": "COMPANY-A",
                "X-Company-Id": "COMPANY-A",
                "X-Mock-User-Id": "U-AGENT",
                "X-Scope-Type": "project",
                "X-Authorized-Project-Ids": "P001",
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["execution_mode"] == "controlled_execute"
        assert data["dag_status"] == "succeeded"
        assert data["dag_execution_allowed"] is True
        read_steps = [step for step in data["step_results"] if step["tool_name"] == "work_orders.read"]
        assert read_steps
        assert read_steps[0]["status"] == "executed"
        assert read_steps[0]["output_summary"]["row_count"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_agent_ask_controlled_execute_runs_broader_read_only_tools():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)
    db.add_all(
        [
            ProjectRiskProfile(
                project_id="P001",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P001",
                calc_date=dt.date(2026, 6, 6),
                total_risk_score=75.0,
                risk_level="high",
                confidence_level="medium",
            ),
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
            ),
            Hazard(
                hazard_id="H-API-DAG-001",
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P001",
                project_id="P001",
                hazard_type="edge_protection",
                hazard_level="major",
                description="Missing edge protection",
                status="open",
                due_date=dt.date(2026, 6, 12),
                is_major=True,
                work_order_id="WO-API-DAG-001",
            ),
            MetricCatalog(
                company_id="COMPANY-A",
                project_id=None,
                metric_code="PROJECT_RISK_SCORE",
                metric_name="Project Risk Score",
                business_definition="Composite project risk score.",
                calculation_formula="weighted_sum",
                source_tables=["project_risk_profile"],
                source_fields=["total_risk_score"],
                aliases=["risk score"],
                status="enabled",
            ),
        ]
    )
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        cases = [
            ("explain project profile risk score", "profile.read"),
            ("explain SR-PROJ-001 rule trigger evidence", "rules.read_triggers"),
            ("explain this hazard rectification evidence", "hazards.read"),
            ("list metric catalog aliases", "metrics.read_catalog"),
        ]
        for message, expected_tool in cases:
            response = client.post(
                "/api/v1/agent/ask",
                json={
                    "message": message,
                    "execution_mode": "controlled_execute",
                    "context": {"project_id": "P001"},
                },
                headers={
                    "X-Tenant-Id": "COMPANY-A",
                    "X-Company-Id": "COMPANY-A",
                    "X-Mock-User-Id": "U-AGENT",
                    "X-Scope-Type": "project",
                    "X-Authorized-Project-Ids": "P001",
                },
            )

            assert response.status_code == 200
            data = response.json()["data"]
            steps = [step for step in data["step_results"] if step["tool_name"] == expected_tool]
            assert steps
            assert steps[0]["status"] == "executed"
            assert steps[0]["output_summary"]["row_count"] == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
