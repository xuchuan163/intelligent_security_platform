from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.session import Base, get_db
from app.main import app
from app.services.auth.seed_rbac import seed_rbac_foundation


def _client_with_db() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    seed_rbac_foundation(db)
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


def _login(client: TestClient, user_id: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"user_id": user_id, "password": settings.demo_default_password, "tenant_id": "CSCEC"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_platform_admin_can_access_metrics_catalog(monkeypatch):
    monkeypatch.setattr(settings, "rbac_enforce", True)
    for client, _ in _client_with_db():
        token = _login(client, "mock-admin")
        response = client.get(
            "/api/v1/metrics/catalog",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


def test_project_officer_denied_metrics_catalog(monkeypatch):
    monkeypatch.setattr(settings, "rbac_enforce", True)
    for client, _ in _client_with_db():
        token = _login(client, "U-PM-P001")
        response = client.get(
            "/api/v1/metrics/catalog",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
        assert response.json()["code"] == "40301"


def test_company_analyst_denied_agent_approvals(monkeypatch):
    monkeypatch.setattr(settings, "rbac_enforce", True)
    for client, _ in _client_with_db():
        token = _login(client, "U-CO-ANALYST")
        response = client.get(
            "/api/v1/agent/approvals",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


def test_project_officer_can_access_work_orders(monkeypatch):
    monkeypatch.setattr(settings, "rbac_enforce", True)
    for client, _ in _client_with_db():
        token = _login(client, "U-PM-P001")
        response = client.get(
            "/api/v1/work-orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200


def test_mock_platform_admin_header_still_accesses_dashboard(monkeypatch):
    monkeypatch.setattr(settings, "rbac_enforce", True)
    for client, _ in _client_with_db():
        response = client.get(
            "/api/v1/dashboard/overview",
            headers={
                "X-Mock-User-Id": "mock-admin",
                "X-Role": "platform_admin",
                "X-Tenant-Id": "CSCEC",
            },
        )
        assert response.status_code == 200
