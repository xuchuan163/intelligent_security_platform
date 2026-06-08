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


def test_login_returns_jwt_and_permission_bundle():
    for client, _ in _client_with_db():
        response = client.post(
            "/api/v1/auth/login",
            json={"user_id": "mock-admin", "password": settings.demo_default_password, "tenant_id": "CSCEC"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert body["data"]["token_type"] == "bearer"
        assert body["data"]["access_token"]
        assert body["data"]["refresh_token"]
        assert body["data"]["user"]["role"] == "platform_admin"
        assert "auth.admin" in body["data"]["user"]["permissions"]
        assert body["data"]["user"]["auth_source"] == "jwt"


def test_login_rejects_invalid_password():
    for client, _ in _client_with_db():
        response = client.post(
            "/api/v1/auth/login",
            json={"user_id": "mock-admin", "password": "wrong-password", "tenant_id": "CSCEC"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == "40101"


def test_refresh_issues_new_access_token():
    for client, _ in _client_with_db():
        login_response = client.post(
            "/api/v1/auth/login",
            json={"user_id": "U-PM-P001", "password": settings.demo_default_password},
        )
        refresh_token = login_response.json()["data"]["refresh_token"]
        refresh_response = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_response.status_code == 200
        data = refresh_response.json()["data"]
        assert data["access_token"]
        assert data["user"]["user_id"] == "U-PM-P001"
        assert data["user"]["authorized_project_ids"] == ["P001"]
        assert "work_orders.write" in data["user"]["permissions"]


def test_me_accepts_bearer_token():
    for client, _ in _client_with_db():
        login_response = client.post(
            "/api/v1/auth/login",
            json={"user_id": "mock-admin", "password": settings.demo_default_password},
        )
        access_token = login_response.json()["data"]["access_token"]
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_response.status_code == 200
        user = me_response.json()["data"]
        assert user["user_id"] == "mock-admin"
        assert user["auth_source"] == "jwt"
        assert "platform_admin" in user["roles"]


def test_me_requires_bearer_when_auth_mode_is_jwt(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "jwt")
    monkeypatch.setattr(settings, "auth_allow_mock_headers", False)

    for client, _ in _client_with_db():
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 401

        login_response = client.post(
            "/api/v1/auth/login",
            json={"user_id": "mock-admin", "password": settings.demo_default_password},
        )
        access_token = login_response.json()["data"]["access_token"]
        me_response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert me_response.status_code == 200


def test_login_rejects_disabled_user():
    for client, db in _client_with_db():
        from app.infrastructure.database.models import UserAccount

        account = db.query(UserAccount).filter(UserAccount.user_id == "mock-admin").one()
        account.status = "disabled"
        db.commit()

        response = client.post(
            "/api/v1/auth/login",
            json={"user_id": "mock-admin", "password": settings.demo_default_password},
        )
        assert response.status_code == 401
