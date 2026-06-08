from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.session import Base, get_db
from app.main import app
from app.services.webhooks.wecom import WecomDeliveryResult


def _client_with_db() -> Iterator[TestClient]:
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
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def _admin_headers() -> dict[str, str]:
    return {
        "X-Mock-User-Id": "mock-admin",
        "X-Tenant-Id": "CSCEC",
        "X-Org-Path": "CSCEC",
        "X-Role": "platform_admin",
    }


def test_webhook_test_route(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "rbac_enforce", True)
    monkeypatch.setattr(settings, "webhook_enabled", True)

    def fake_send(*args, **kwargs):
        return WecomDeliveryResult(
            response_status_code=200,
            response_body='{"errcode":0,"errmsg":"ok"}',
            delivery_status="success",
            error_message=None,
            elapsed_ms=12,
        )

    monkeypatch.setattr("app.services.webhooks.dispatch.send_wecom_bot_message", fake_send)

    for client in _client_with_db():
        denied = client.post(
            "/api/v1/webhooks/test",
            json={"message": "test", "target_url": "https://example.com/hook?key=1"},
            headers={
                "X-Mock-User-Id": "viewer",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "company_analyst",
            },
        )
        assert denied.status_code == 403

        response = client.post(
            "/api/v1/webhooks/test",
            json={
                "message": "沙箱测试",
                "project_id": "P001",
                "target_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SANDBOX",
            },
            headers=_admin_headers(),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert body["data"]["delivery_status"] == "success"
        assert body["data"]["delivery_id"].startswith("WHDL-")


def test_webhook_dispatch_rule_trigger_route(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "rbac_enforce", True)
    monkeypatch.setattr(settings, "webhook_enabled", True)

    def fake_dispatch(*args, **kwargs):
        return {
            "delivery_id": "WHDL-FAKE000001",
            "delivery_status": "success",
            "event_id": "evt-1",
            "event_type": "alert.profile",
            "trigger_id": kwargs["trigger_id"],
            "rule_id": "SR-PROJ-001",
            "need_human_review": False,
        }

    monkeypatch.setattr(
        "app.api.v1.endpoints.webhooks.dispatch_rule_trigger_webhook",
        fake_dispatch,
    )

    for client in _client_with_db():
        response = client.post(
            "/api/v1/webhooks/dispatch/rule-trigger",
            json={"trigger_id": "RT-000001"},
            headers=_admin_headers(),
        )
        assert response.status_code == 200
        assert response.json()["data"]["trigger_id"] == "RT-000001"


def test_webhook_dispatch_work_order_overdue_route(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "rbac_enforce", True)
    monkeypatch.setattr(settings, "webhook_enabled", True)

    monkeypatch.setattr(
        "app.api.v1.endpoints.webhooks.dispatch_work_order_overdue_webhook",
        lambda *args, **kwargs: {
            "total": 1,
            "work_order_ids": ["WO-OVER-001"],
            "dispatched": [{"delivery_id": "WHDL-FAKE000002", "delivery_status": "success"}],
        },
    )

    for client in _client_with_db():
        response = client.post(
            "/api/v1/webhooks/dispatch/work-order-overdue",
            json={"scan": True},
            headers=_admin_headers(),
        )
        assert response.status_code == 200
        assert response.json()["data"]["total"] == 1
