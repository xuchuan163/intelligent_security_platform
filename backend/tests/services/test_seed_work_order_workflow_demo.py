from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import Hazard, Project, ProjectUser, SafetyWorkOrder, Tenant, WorkOrderFlowLog
from app.infrastructure.database.session import Base
from scripts.seed_demo_data import seed_work_order_workflow_demo


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _seed_project(db) -> None:
    db.add(Tenant(tenant_id="CSCEC", tenant_name="CSCEC"))
    db.add(
        Project(
            project_id="P002",
            tenant_id="CSCEC",
            company_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P002",
            project_name="Wuhan Center",
            status="active",
        )
    )
    db.commit()


def test_seed_work_order_workflow_demo_adds_roles_hazard_order_and_flow_log_idempotently():
    db = _session()
    _seed_project(db)

    seed_work_order_workflow_demo(db)
    seed_work_order_workflow_demo(db)

    roles = {
        (row.user_id, row.role_code, row.subcontractor_id)
        for row in db.query(ProjectUser).filter(ProjectUser.project_id == "P002").all()
    }
    assert {
        ("U-GC-01", "gc_safety_officer", None),
        ("U-DIR-01", "safety_director", None),
        ("U-SUB-S003", "sub_safety_officer", "S003"),
    } <= roles

    hazard = db.query(Hazard).filter(Hazard.hazard_id == "H-DEMO-P002-001").one()
    order = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == "WO-DEMO-P002-001").one()
    flow_log = db.query(WorkOrderFlowLog).filter(
        WorkOrderFlowLog.work_order_id == "WO-DEMO-P002-001",
        WorkOrderFlowLog.action == "create",
    ).one()

    assert hazard.project_id == "P002"
    assert hazard.subcontractor_id == "S003"
    assert hazard.work_order_id == "WO-DEMO-P002-001"
    assert hazard.attachments["items"][0]["phase"] == "discovery"

    assert order.project_id == "P002"
    assert order.subcontractor_id == "S003"
    assert order.status == "pending_confirm"
    assert order.source_type == "hazard"
    assert order.source_id == "H-DEMO-P002-001"
    assert order.attachments == hazard.attachments

    assert flow_log.from_status is None
    assert flow_log.to_status == "pending_confirm"
    assert flow_log.operator_user_id == "U-GC-01"
