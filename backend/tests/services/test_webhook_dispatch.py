import datetime as dt

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import RuleTriggerLog, SafetyWorkOrder, WebhookDeliveryLog
from app.infrastructure.database.session import Base
from app.services.webhooks.dispatch import (
    WebhookDispatchError,
    dispatch_rule_trigger_webhook,
    dispatch_work_order_overdue_webhook,
)
from app.services.webhooks.wecom import WecomDeliveryResult


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
        user_id="U-WH-DISPATCH",
        user_name="Dispatch Approver",
        tenant_id="CSCEC",
        company_id="CSCEC",
        org_path="CSCEC",
        role="project_safety_officer",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
        permissions=("agent.approve",),
    )


def _fake_success_result(*args, **kwargs) -> WecomDeliveryResult:
    return WecomDeliveryResult(
        response_status_code=200,
        response_body='{"errcode":0,"errmsg":"ok"}',
        delivery_status="success",
        error_message=None,
        elapsed_ms=8,
    )


def test_dispatch_rule_trigger_webhook_records_delivery(monkeypatch):
    monkeypatch.setattr(settings, "webhook_enabled", True)
    monkeypatch.setattr(
        "app.services.webhooks.dispatch.send_wecom_bot_message",
        _fake_success_result,
    )

    engine, db = _session()
    try:
        db.add(
            RuleTriggerLog(
                rule_id="SR-PROJ-001",
                tenant_id="CSCEC",
                org_path="CSCEC/CSCEC-8B/P001",
                object_type="project",
                object_id="P001",
                project_id="P001",
                trigger_condition="major_hazard_overdue_count=1",
                evidence={"count": 1},
                severity="high",
                risk_action="upgrade_to_high",
            )
        )
        db.commit()
        trigger = db.query(RuleTriggerLog).first()
        assert trigger is not None

        result = dispatch_rule_trigger_webhook(
            db,
            trigger_id=f"RT-{trigger.id:06d}",
            current_user=_approver(),
            target_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SANDBOX",
        )
        assert result["delivery_status"] == "success"
        assert result["event_type"] == "alert.profile"
        assert result["rule_id"] == "SR-PROJ-001"
        assert result["need_human_review"] is False

        row = db.query(WebhookDeliveryLog).filter_by(delivery_id=result["delivery_id"]).one()
        assert row.event_type == "alert.profile"
        assert row.project_id == "P001"
    finally:
        db.close()
        engine.dispose()


def test_dispatch_work_order_overdue_webhook_scan_mode(monkeypatch):
    monkeypatch.setattr(settings, "webhook_enabled", True)
    monkeypatch.setattr(
        "app.services.webhooks.dispatch.send_wecom_bot_message",
        _fake_success_result,
    )

    engine, db = _session()
    try:
        overdue_time = dt.datetime.utcnow() - dt.timedelta(days=1)
        db.add(
            SafetyWorkOrder(
                work_order_id="WO-OVER-001",
                tenant_id="CSCEC",
                org_path="CSCEC/CSCEC-8B/P001",
                work_order_type="rectification",
                project_id="P001",
                title="超期整改单",
                status="processing",
                priority="critical",
                due_time=overdue_time,
            )
        )
        db.add(
            SafetyWorkOrder(
                work_order_id="WO-OPEN-001",
                tenant_id="CSCEC",
                org_path="CSCEC/CSCEC-8B/P001",
                work_order_type="rectification",
                project_id="P001",
                title="未超期单",
                status="processing",
                priority="normal",
                due_time=dt.datetime.utcnow() + dt.timedelta(days=2),
            )
        )
        db.commit()

        result = dispatch_work_order_overdue_webhook(
            db,
            current_user=_approver(),
            scan=True,
            target_url="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=SANDBOX",
        )
        assert result["total"] == 1
        assert result["work_order_ids"] == ["WO-OVER-001"]
        assert result["dispatched"][0]["need_human_review"] is True
    finally:
        db.close()
        engine.dispose()


def test_dispatch_work_order_overdue_requires_selector():
    engine, db = _session()
    try:
        with pytest.raises(WebhookDispatchError) as exc:
            dispatch_work_order_overdue_webhook(db, current_user=_approver())
        assert exc.value.status_code == 422
    finally:
        db.close()
        engine.dispose()
