from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.agent import get_redis_client_optional
from app.core.config import settings
from app.infrastructure.database.models import AgentNl2sqlAudit, Project
from app.infrastructure.database.session import Base, get_db
from app.main import app


@pytest.fixture()
def api_client(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    db.add_all(
        [
            Project(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P001",
                project_id="P001",
                project_name="Project One",
                status="active",
            ),
            Project(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                project_name="Project Two",
                status="active",
            ),
        ]
    )
    db.commit()
    monkeypatch.setattr(settings, "app_env", "local")
    monkeypatch.setattr(settings, "nl2sql_provider", "disabled")

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis_client_optional] = lambda: None
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_redis_client_optional, None)
        db.close()
        engine.dispose()


def _headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": "COMPANY-A",
        "X-Company-Id": "COMPANY-A",
        "X-Mock-User-Id": "U-NL2SQL",
        "X-Scope-Type": "company",
    }


def test_disabled_provider_returns_generation_failed_and_audit_row(api_client):
    client, db = api_client

    response = client.post(
        "/api/v1/agent/nl2sql",
        json={"question": "查询项目列表"},
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "generation_failed"
    assert data["allowed"] is False
    assert data["execution_status"] == "generation_failed"
    assert data["rows"] == []
    assert db.query(AgentNl2sqlAudit).count() == 1


def test_local_mock_provider_can_audit_without_execution(api_client):
    client, db = api_client

    response = client.post(
        "/api/v1/agent/nl2sql",
        json={
            "question": "查询项目列表",
            "provider": "mock",
            "mock_llm_output": "SELECT project_id, project_name FROM project",
        },
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "audit_passed"
    assert data["allowed"] is True
    assert data["execution_status"] == "audited"
    assert data["rows"] == []
    assert "company_id" in data["sanitized_sql"]
    assert db.query(AgentNl2sqlAudit).count() == 1


def test_local_mock_provider_can_execute_readonly_sql(api_client):
    client, db = api_client

    response = client.post(
        "/api/v1/agent/nl2sql",
        json={
            "question": "查询项目列表",
            "execute": True,
            "provider": "mock",
            "mock_llm_output": "SELECT project_id, project_name FROM project",
        },
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "executed"
    assert data["allowed"] is True
    assert data["execution_status"] == "executed"
    assert data["row_count"] == 2
    assert data["columns"] == ["project_id", "project_name"]
    assert db.query(AgentNl2sqlAudit).count() == 1


def test_unsafe_sql_is_rejected_and_not_executed(api_client):
    client, db = api_client

    response = client.post(
        "/api/v1/agent/nl2sql",
        json={
            "question": "删除项目",
            "execute": True,
            "provider": "mock",
            "mock_llm_output": "DELETE FROM project",
        },
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] in {"invalid_output", "audit_rejected"}
    assert data["allowed"] is False
    assert data["execution_status"] == data["status"]
    assert data["rows"] == []
    assert db.query(Project).count() == 2
    assert db.query(AgentNl2sqlAudit).count() == 1


def test_ambiguous_question_returns_clarification_session(api_client):
    client, db = api_client

    response = client.post(
        "/api/v1/agent/nl2sql",
        json={
            "question": "查询最近风险较高的项目",
            "provider": "mock",
            "mock_llm_output": "CLARIFICATION_REQUIRED: please provide a time range and risk definition",
        },
        headers=_headers(),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "clarification_required"
    assert data["awaiting_clarification"] is True
    assert data["clarification_id"].startswith("NL2SQL-CLR-")
    assert "time range" in data["clarification_prompt"]
    assert db.query(AgentNl2sqlAudit).count() == 1


def test_clarification_follow_up_can_audit_after_user_reply(api_client):
    client, db = api_client

    first = client.post(
        "/api/v1/agent/nl2sql",
        json={
            "question": "查询最近风险较高的项目",
            "provider": "mock",
            "mock_llm_output": "CLARIFICATION_REQUIRED: please provide a time range and risk definition",
        },
        headers=_headers(),
    )
    clarification_id = first.json()["data"]["clarification_id"]

    second = client.post(
        "/api/v1/agent/nl2sql",
        json={
            "clarification_id": clarification_id,
            "clarification_reply": "最近30天，高风险指 risk_level=high",
            "provider": "mock",
            "mock_llm_output": "SELECT project_id, risk_level FROM project_risk_profile WHERE risk_level = 'high'",
        },
        headers=_headers(),
    )

    assert second.status_code == 200
    data = second.json()["data"]
    assert data["status"] == "audit_passed"
    assert data["awaiting_clarification"] is False
    assert data["turn"] == 2
    assert "最近30天" in data["refined_question"]
    assert data["clarification_id"] == clarification_id
    assert db.query(AgentNl2sqlAudit).count() == 2


def test_mock_provider_override_is_blocked_outside_local_env(api_client, monkeypatch):
    client, db = api_client
    monkeypatch.setattr(settings, "app_env", "prod")

    response = client.post(
        "/api/v1/agent/nl2sql",
        json={
            "question": "查询项目列表",
            "provider": "mock",
            "mock_llm_output": "SELECT project_id FROM project",
        },
        headers=_headers(),
    )

    assert response.status_code == 403
    assert db.query(AgentNl2sqlAudit).count() == 0
