import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import SafetyWorkOrder
from app.infrastructure.database.session import Base, get_db
from app.main import app
from app.services.work_orders.service import escalate_overdue_work_orders


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _add_order(
    db,
    work_order_id: str,
    status: str,
    due_time: dt.datetime | None,
    updated_at: dt.datetime,
) -> None:
    db.add(
        SafetyWorkOrder(
            work_order_id=work_order_id,
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-ESC",
            work_order_type="hazard_rectification",
            source_type="manual",
            source_id=work_order_id,
            project_id="P-ESC",
            title=f"Escalation test {work_order_id}",
            status=status,
            priority="normal",
            due_time=due_time,
            updated_at=updated_at,
        )
    )


def test_escalate_overdue_work_orders_only_updates_overdue_processing_orders():
    db = _session()
    now = dt.datetime(2026, 6, 3, 10, 0, 0)
    _add_order(db, "WO-OVERDUE", "processing", now - dt.timedelta(hours=1), now - dt.timedelta(hours=5))
    _add_order(db, "WO-FUTURE", "processing", now + dt.timedelta(hours=1), now - dt.timedelta(hours=5))
    _add_order(db, "WO-DISPATCHED", "dispatched", now - dt.timedelta(hours=1), now - dt.timedelta(hours=5))
    db.commit()

    result = escalate_overdue_work_orders(db, now=now)

    overdue = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == "WO-OVERDUE").one()
    future = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == "WO-FUTURE").one()
    dispatched = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == "WO-DISPATCHED").one()

    assert result == {
        "scanned_work_orders": 2,
        "escalated_work_orders": 1,
        "skipped_work_orders": 1,
        "work_order_ids": ["WO-OVERDUE"],
    }
    assert overdue.status == "overdue_escalated"
    assert overdue.escalation_level == 1
    assert overdue.escalation_history["events"][0]["action"] == "timeout"
    assert future.status == "processing"
    assert dispatched.status == "dispatched"


def test_escalate_overdue_work_orders_api_updates_overdue_orders():
    db = _session()
    now = dt.datetime.utcnow()
    _add_order(db, "WO-API-OVERDUE", "processing", now - dt.timedelta(hours=1), now - dt.timedelta(hours=5))
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).post(
            "/api/v1/work-orders/escalate-overdue",
            headers={
                "X-Tenant-Id": "TENANT-A",
                "X-Org-Path": "TENANT-A/BU-01",
                "X-Data-Scope": "org",
            },
        )
    finally:
        app.dependency_overrides.clear()

    order = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == "WO-API-OVERDUE").one()

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["code"] == "SUCCESS"
    assert body["data"]["escalated_work_orders"] == 1
    assert order.status == "overdue_escalated"
