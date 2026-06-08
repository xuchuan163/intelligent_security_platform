import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import Hazard, Project, ProjectUser, SafetyWorkOrder, WorkOrderFlowLog
from app.infrastructure.database.session import Base
from app.schemas.hazards import HazardCreatePayload
from app.services.hazards.service import create_hazard_with_work_order


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _gc_user(role: str = "gc_safety_officer") -> MockUser:
    return MockUser(
        user_id="U-GC-01",
        user_name="李安全",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        role=role,
        data_scope=DataScope.ORG,
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P002",),
    )


def _payload() -> HazardCreatePayload:
    return HazardCreatePayload(
        description="基坑东侧临边防护缺失，存在坠落风险",
        hazard_type="临边防护",
        hazard_level="major",
        subcontractor_id="S003",
        due_date=dt.date(2026, 6, 12),
        location="基坑东侧",
    )


def _seed_base(db) -> None:
    db.add(
        Project(
            project_id="P002",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P002",
            project_name="武汉长江中心",
            status="active",
        )
    )
    db.add(
        ProjectUser(
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P002",
            project_id="P002",
            user_id="U-GC-01",
            user_name="李安全",
            role_code="gc_safety_officer",
        )
    )
    db.commit()


def test_create_hazard_with_work_order_rejects_non_gc_or_missing_images():
    db = _session()
    _seed_base(db)

    with pytest.raises(PermissionError, match="Project role is not authorized"):
        create_hazard_with_work_order(
            db,
            project_id="P002",
            payload=_payload(),
            discovery_attachments=[{"file_id": "F-1"}],
            current_user=_gc_user(role="safety_director"),
        )

    with pytest.raises(ValueError, match="At least one discovery image is required"):
        create_hazard_with_work_order(
            db,
            project_id="P002",
            payload=_payload(),
            discovery_attachments=[],
            current_user=_gc_user(),
        )


def test_create_hazard_with_work_order_creates_hazard_order_and_flow_log():
    db = _session()
    _seed_base(db)
    attachment = {
        "file_id": "F-001",
        "phase": "discovery",
        "content_type": "image/jpeg",
        "url": "/api/v1/files/F-001",
    }

    result = create_hazard_with_work_order(
        db,
        project_id="P002",
        payload=_payload(),
        discovery_attachments=[attachment],
        current_user=_gc_user(),
    )

    hazard = db.query(Hazard).one()
    order = db.query(SafetyWorkOrder).one()
    flow = db.query(WorkOrderFlowLog).one()

    assert result["hazard_id"] == hazard.hazard_id
    assert result["work_order_id"] == order.work_order_id
    assert result["status"] == "open"
    assert result["work_order_status"] == "pending_confirm"

    assert hazard.project_id == "P002"
    assert hazard.company_id == "COMPANY-A"
    assert hazard.discovered_by_user_id == "U-GC-01"
    assert hazard.attachments == {"items": [attachment]}
    assert hazard.work_order_id == order.work_order_id

    assert order.source_type == "hazard"
    assert order.source_id == hazard.hazard_id
    assert order.project_id == "P002"
    assert order.subcontractor_id == "S003"
    assert order.status == "pending_confirm"
    assert order.attachments == {"items": [attachment]}

    assert flow.work_order_id == order.work_order_id
    assert flow.from_status is None
    assert flow.to_status == "pending_confirm"
    assert flow.action == "create"
    assert flow.operator_user_id == "U-GC-01"
    assert flow.operator_role == "gc_safety_officer"
    assert flow.attachments == {"items": [attachment]}
