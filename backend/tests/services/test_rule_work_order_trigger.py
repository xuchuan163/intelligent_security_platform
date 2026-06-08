import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import Hazard, Project, SafetyWorkOrder, Worker
from app.infrastructure.database.session import Base
from app.services.profiles.service import recalculate_project_profiles
from app.services.profiles.service import recalculate_worker_profiles


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_project_rule_trigger_creates_one_deduplicated_work_order():
    db = _session()
    today = dt.date.today()
    db.add(
        Project(
            project_id="P-AUTO",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-AUTO",
            project_name="Auto Work Order Project",
            status="active",
            schedule_pressure_index=5,
        )
    )
    db.add(
        Hazard(
            hazard_id="HZ-AUTO-001",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-AUTO",
            project_id="P-AUTO",
            hazard_type="major",
            hazard_level="major",
            description="overdue major hazard",
            status="open",
            due_date=today - dt.timedelta(days=1),
            is_major=True,
        )
    )
    db.commit()

    first = recalculate_project_profiles(db)
    second = recalculate_project_profiles(db)

    orders = db.query(SafetyWorkOrder).all()
    assert first["created_work_orders"] == 1
    assert first["skipped_duplicate_work_orders"] == 0
    assert second["created_work_orders"] == 0
    assert second["skipped_duplicate_work_orders"] == 1
    assert len(orders) == 1
    assert orders[0].rule_id == "SR-PROJ-001"
    assert orders[0].source_type == "project"
    assert orders[0].source_id == "P-AUTO"
    assert orders[0].status == "pending_confirm"
    assert orders[0].priority == "urgent"


def test_worker_rule_trigger_creates_deduplicated_work_orders():
    db = _session()
    db.add(
        Worker(
            worker_id="W-AUTO",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-AUTO",
            project_id="P-AUTO",
            subcontractor_id="SUB-AUTO",
            worker_name_masked="Worker Auto",
            exam_score=80,
            violation_count_30d=3,
            special_cert_status="expired",
            health_check_status="valid",
            entry_days=30,
            status="active",
        )
    )
    db.commit()

    first = recalculate_worker_profiles(db)
    second = recalculate_worker_profiles(db)

    orders = db.query(SafetyWorkOrder).order_by(SafetyWorkOrder.rule_id).all()
    assert first["created_work_orders"] == 2
    assert first["skipped_duplicate_work_orders"] == 0
    assert second["created_work_orders"] == 0
    assert second["skipped_duplicate_work_orders"] == 2
    assert [order.rule_id for order in orders] == ["SR-WORKER-001", "SR-WORKER-005"]
    assert {order.source_type for order in orders} == {"worker"}
    assert {order.source_id for order in orders} == {"W-AUTO"}
