import datetime as dt
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base, get_db
from app.main import app


def _client_with_db() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    db.add(
        AccidentCaseLibrary(
            accident_case_id="AC-RAG-001",
            tenant_id="CSCEC",
            accident_type="触电",
            severity="一般事故",
            direct_cause="配电箱接地失效",
            indirect_cause="巡检不足",
            rectification_measures="更换漏保",
            tags=["临时用电"],
            status="active",
            created_at=dt.datetime(2026, 6, 1, 9, 0, 0),
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
        yield TestClient(app), db
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_rag_search_requires_agent_ask_permission(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "rbac_enforce", True)
    monkeypatch.setattr(settings, "milvus_enabled", False)
    for client, _ in _client_with_db():
        denied = client.post(
            "/api/v1/rag/search",
            json={"query": "触电"},
            headers={
                "X-Mock-User-Id": "viewer-no-agent",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "viewer",
            },
        )
        assert denied.status_code == 403

        allowed = client.post(
            "/api/v1/rag/search",
            json={"query": "触电"},
            headers={
                "X-Mock-User-Id": "mock-admin",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "platform_admin",
            },
        )
        assert allowed.status_code == 200
        data = allowed.json()["data"]
        assert data["mode"] == "mysql_keyword"
        assert data["total"] >= 1


def test_rag_search_rejects_empty_query(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "rbac_enforce", False)
    for client, _ in _client_with_db():
        response = client.post("/api/v1/rag/search", json={"query": ""})
        assert response.status_code == 422
