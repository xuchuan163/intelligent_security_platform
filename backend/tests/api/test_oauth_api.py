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


def test_oauth_authorize_returns_mock_authorize_url(monkeypatch):
    monkeypatch.setattr(settings, "oauth_enabled", False)
    monkeypatch.setattr(settings, "oauth_mock_enabled", True)
    for client, _ in _client_with_db():
        response = client.get("/api/v1/auth/oauth/authorize")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["mode"] == "mock"
        assert "MOCK_AUTHORIZED" in data["authorize_url"]
        assert data["state"]


def test_oauth_authorize_redirects_in_mock_mode(monkeypatch):
    monkeypatch.setattr(settings, "oauth_enabled", False)
    monkeypatch.setattr(settings, "oauth_mock_enabled", True)
    for client, _ in _client_with_db():
        response = client.get("/api/v1/auth/oauth/authorize?redirect=true", follow_redirects=False)
        assert response.status_code == 302
        assert "code=MOCK_AUTHORIZED" in response.headers["location"]


def test_oauth_callback_mock_code_issues_jwt_tokens(monkeypatch):
    monkeypatch.setattr(settings, "oauth_enabled", False)
    monkeypatch.setattr(settings, "oauth_mock_enabled", True)
    for client, _ in _client_with_db():
        response = client.get(
            "/api/v1/auth/oauth/callback",
            params={"code": settings.oauth_mock_code, "state": "demo-state"},
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["access_token"]
        assert data["user"]["user_id"] == settings.oauth_mock_user_id
        assert data["oauth"]["mode"] == "mock"


def test_oauth_callback_rejects_invalid_mock_code(monkeypatch):
    monkeypatch.setattr(settings, "oauth_enabled", False)
    monkeypatch.setattr(settings, "oauth_mock_enabled", True)
    for client, _ in _client_with_db():
        response = client.get("/api/v1/auth/oauth/callback", params={"code": "WRONG"})
        assert response.status_code == 401


def test_oauth_authorize_returns_501_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "oauth_enabled", False)
    monkeypatch.setattr(settings, "oauth_mock_enabled", False)
    for client, _ in _client_with_db():
        response = client.get("/api/v1/auth/oauth/authorize")
        assert response.status_code == 501
        assert response.json()["code"] == "50101"


def test_oauth_callback_live_mode_returns_501(monkeypatch):
    monkeypatch.setattr(settings, "oauth_enabled", True)
    monkeypatch.setattr(settings, "oauth_mock_enabled", False)
    for client, _ in _client_with_db():
        response = client.get("/api/v1/auth/oauth/callback", params={"code": "real-code"})
        assert response.status_code == 501
