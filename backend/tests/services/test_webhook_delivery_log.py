import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import WebhookDeliveryLog
from app.infrastructure.database.session import Base
from app.services.webhooks.delivery_log import (
    create_delivery_log,
    finalize_delivery_log,
    list_delivery_logs,
    mask_webhook_url,
    record_webhook_delivery,
)


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def _company_user() -> MockUser:
    return MockUser(
        user_id="U-WH-01",
        user_name="Webhook Tester",
        tenant_id="CSCEC",
        company_id="CSCEC",
        org_path="CSCEC",
        role="platform_admin",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def test_mask_webhook_url_hides_sensitive_query_params():
    masked = mask_webhook_url(
        "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SECRET-123&debug=1"
    )
    assert masked is not None
    assert "SECRET-123" not in masked
    assert "key=" in masked and "***" in masked
    assert "debug=1" in masked


def test_create_and_finalize_delivery_log():
    engine, db = _session()
    try:
        created = create_delivery_log(
            db,
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P001",
            event_type="work_order.status_changed",
            request_payload={
                "event_type": "work_order.status_changed",
                "event_id": "evt-001",
                "data": {"work_order_id": "WO001"},
            },
            channel="wecom_bot",
            target_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SECRET",
            project_id="P001",
            triggered_by="U-WH-01",
        )
        assert created["delivery_id"].startswith("WHDL-")
        assert created["delivery_status"] == "pending"
        assert created["target_url_masked"] is not None
        assert "SECRET" not in created["target_url_masked"]

        finalized = finalize_delivery_log(
            db,
            created["delivery_id"],
            delivery_status="success",
            response_status_code=200,
            response_body='{"errcode":0,"errmsg":"ok"}',
            elapsed_ms=120,
        )
        assert finalized is not None
        assert finalized["delivery_status"] == "success"
        assert finalized["response_status_code"] == 200
        assert finalized["delivered_at"] is not None
    finally:
        db.close()
        engine.dispose()


def test_record_webhook_delivery_persists_failed_attempt():
    engine, db = _session()
    try:
        result = record_webhook_delivery(
            db,
            tenant_id="CSCEC",
            org_path="CSCEC",
            event_type="hazard.overdue",
            request_payload={"event_id": "evt-002", "data": {"hazard_id": "H002"}},
            delivery_status="failed",
            response_status_code=500,
            error_message="upstream timeout",
            need_human_review=True,
            triggered_by="system",
        )
        row = db.query(WebhookDeliveryLog).filter_by(delivery_id=result["delivery_id"]).one()
        assert row.delivery_status == "failed"
        assert row.need_human_review is True
        assert row.error_message == "upstream timeout"
    finally:
        db.close()
        engine.dispose()


def test_list_delivery_logs_filters_by_status():
    engine, db = _session()
    try:
        record_webhook_delivery(
            db,
            tenant_id="CSCEC",
            org_path="CSCEC",
            event_type="work_order.status_changed",
            request_payload={"event_id": "evt-003"},
            delivery_status="success",
            project_id="P001",
        )
        record_webhook_delivery(
            db,
            tenant_id="CSCEC",
            org_path="CSCEC",
            event_type="hazard.overdue",
            request_payload={"event_id": "evt-004"},
            delivery_status="failed",
            project_id="P002",
        )

        success_rows = list_delivery_logs(
            db,
            delivery_status="success",
            current_user=_company_user(),
        )
        assert len(success_rows) == 1
        assert success_rows[0]["event_type"] == "work_order.status_changed"
    finally:
        db.close()
        engine.dispose()


def test_finalize_delivery_log_rejects_invalid_status():
    engine, db = _session()
    try:
        created = create_delivery_log(
            db,
            tenant_id="CSCEC",
            org_path="CSCEC",
            event_type="alert.profile",
            request_payload={"event_id": "evt-005"},
        )
        with pytest.raises(ValueError):
            finalize_delivery_log(db, created["delivery_id"], delivery_status="pending")
    finally:
        db.close()
        engine.dispose()
