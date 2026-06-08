from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import AgentFeedback
from app.infrastructure.database.session import Base, get_db
from app.main import app


def _headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": "COMPANY-A",
        "X-Company-Id": "COMPANY-A",
        "X-Mock-User-Id": "U-FB-API",
        "X-Scope-Type": "company",
    }


def test_post_and_get_agent_feedback_api():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        create_response = client.post(
            "/api/v1/agent/feedback",
            json={
                "task_id": "NLSQL-TEST-001",
                "agent_name": "nl2sql_analyst",
                "feedback_type": "thumb",
                "rating": -1,
                "feedback_reason": "wrong metric",
                "original_output": {"status": "audit_passed"},
                "project_id": "P001",
            },
            headers=_headers(),
        )
        assert create_response.status_code == 200
        created = create_response.json()["data"]
        assert created["feedback_id"].startswith("AGFB-")
        assert created["label_status"] == "pending"

        list_response = client.get(
            "/api/v1/agent/feedback",
            params={"agent_name": "nl2sql_analyst", "task_id": "NLSQL-TEST-001"},
            headers=_headers(),
        )
        assert list_response.status_code == 200
        items = list_response.json()["data"]["items"]
        assert len(items) == 1
        assert db.query(AgentFeedback).count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_post_correction_feedback_requires_payload():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/agent/feedback",
            json={
                "task_id": "AGDAG-TEST",
                "agent_name": "safety_supervisor",
                "feedback_type": "correction",
            },
            headers=_headers(),
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
