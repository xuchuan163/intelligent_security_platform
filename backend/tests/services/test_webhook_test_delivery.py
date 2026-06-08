import json

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import WebhookDeliveryLog
from app.infrastructure.database.session import Base
from app.schemas.webhooks import WebhookTestRequest
from app.services.webhooks.test_delivery import WebhookTestError, send_test_webhook
from app.services.webhooks.wecom import send_wecom_bot_message


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def _approver() -> MockUser:
    return MockUser(
        user_id="U-WH-TEST",
        user_name="Webhook Approver",
        tenant_id="CSCEC",
        company_id="CSCEC",
        org_path="CSCEC",
        role="project_safety_officer",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
        permissions=("agent.approve",),
    )


def test_send_wecom_bot_message_success_with_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = json.loads(request.content.decode())
        assert body["msgtype"] == "text"
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = send_wecom_bot_message(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=TEST",
        message_body={"msgtype": "text", "text": {"content": "hello"}},
        http_client=client,
    )
    assert result.delivery_status == "success"
    assert result.response_status_code == 200


def test_send_test_webhook_records_success_delivery(monkeypatch):
    monkeypatch.setattr(settings, "webhook_enabled", True)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"errcode": 0, "errmsg": "ok"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    engine, db = _session()
    try:
        result = send_test_webhook(
            db,
            request=WebhookTestRequest(
                message="沙箱测试消息",
                project_id="P001",
                target_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SANDBOX",
            ),
            current_user=_approver(),
            http_client=client,
        )
        assert result["delivery_status"] == "success"
        assert result["delivery_id"].startswith("WHDL-")
        assert "SANDBOX" not in (result["target_url_masked"] or "")

        row = db.query(WebhookDeliveryLog).filter_by(delivery_id=result["delivery_id"]).one()
        assert row.channel == "wecom_bot"
        assert row.delivery_status == "success"
        assert row.project_id == "P001"
    finally:
        db.close()
        engine.dispose()


def test_send_test_webhook_requires_url_or_enabled_flag(monkeypatch):
    monkeypatch.setattr(settings, "webhook_enabled", False)
    monkeypatch.setattr(settings, "webhook_wecom_bot_url", None)

    engine, db = _session()
    try:
        with pytest.raises(WebhookTestError) as exc:
            send_test_webhook(
                db,
                request=WebhookTestRequest(message="disabled"),
                current_user=_approver(),
            )
        assert exc.value.status_code == 403
    finally:
        db.close()
        engine.dispose()
