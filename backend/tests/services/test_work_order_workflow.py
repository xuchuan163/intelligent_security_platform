import datetime as dt

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import Hazard, Project, ProjectUser, SafetyWorkOrder, WorkOrderFlowLog
from app.infrastructure.database.session import Base
from app.schemas.work_orders import WorkOrderStatusUpdate
from app.services.work_orders.workflow import transition_work_order


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _user(role: str, user_id: str, subcontractor_id: str | None = None) -> MockUser:
    return MockUser(
        user_id=user_id,
        user_name=user_id,
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        role=role,
        data_scope=DataScope.ORG,
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P002",),
        subcontractor_id=subcontractor_id,
    )


def _seed_base(db, status: str = "pending_confirm") -> SafetyWorkOrder:
    db.add(
        Project(
            project_id="P002",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P002",
            project_name="Wuhan Center",
            status="active",
        )
    )
    db.add_all(
        [
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-GC-01",
                user_name="GC Safety",
                role_code="gc_safety_officer",
            ),
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-DIR-01",
                user_name="Safety Director",
                role_code="safety_director",
            ),
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-SUB-S003",
                user_name="Sub Safety",
                role_code="sub_safety_officer",
                subcontractor_id="S003",
            ),
        ]
    )
    hazard = Hazard(
        hazard_id="H-001",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        project_id="P002",
        subcontractor_id="S003",
        hazard_type="edge_protection",
        hazard_level="major",
        description="Missing edge protection with fall risk.",
        status="open",
        due_date=dt.date(2026, 6, 12),
        is_major=True,
        work_order_id="WO-001",
    )
    order = SafetyWorkOrder(
        work_order_id="WO-001",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        work_order_type="hazard_rectification",
        source_type="hazard",
        source_id="H-001",
        project_id="P002",
        subcontractor_id="S003",
        title="Edge protection rectification",
        description="Missing edge protection with fall risk.",
        priority="high",
        status=status,
        due_time=dt.datetime(2026, 6, 12, 18, 0),
        attachments={"items": [{"file_id": "F-DISCOVERY", "phase": "discovery"}]},
    )
    db.add_all([hazard, order])
    db.commit()
    return order


def test_director_confirm_dispatches_order_and_records_flow_log():
    db = _session()
    _seed_base(db)

    result = transition_work_order(
        db,
        "WO-001",
        WorkOrderStatusUpdate(
            action="confirm",
            assignee_user_id="U-SUB-S003",
            due_time=dt.datetime(2026, 6, 10, 18, 0),
            comment="Dispatch to subcontractor safety officer.",
        ),
        _user("safety_director", "U-DIR-01"),
    )

    order = db.query(SafetyWorkOrder).filter_by(work_order_id="WO-001").one()
    flow = db.query(WorkOrderFlowLog).filter_by(action="confirm").one()

    assert result["new_status"] == "dispatched"
    assert order.status == "dispatched"
    assert order.responsible_user_id == "U-SUB-S003"
    assert order.due_time == dt.datetime(2026, 6, 10, 18, 0)
    assert flow.from_status == "pending_confirm"
    assert flow.to_status == "dispatched"
    assert flow.operator_user_id == "U-DIR-01"


def test_subcontractor_submit_result_requires_rectification_attachment():
    db = _session()
    _seed_base(db, status="processing")

    with pytest.raises(ValueError, match="At least one rectification image is required"):
        transition_work_order(
            db,
            "WO-001",
            WorkOrderStatusUpdate(action="submit_result", comment="Fixed."),
            _user("sub_safety_officer", "U-SUB-S003", subcontractor_id="S003"),
        )


def test_subcontractor_submit_result_rejects_non_rectification_attachment():
    db = _session()
    _seed_base(db, status="processing")

    with pytest.raises(ValueError, match="At least one rectification image is required"):
        transition_work_order(
            db,
            "WO-001",
            WorkOrderStatusUpdate(
                action="submit_result",
                attachments={"items": [{"file_id": "F-DISCOVERY-2", "phase": "discovery"}]},
            ),
            _user("sub_safety_officer", "U-SUB-S003", subcontractor_id="S003"),
        )


def test_gc_review_pass_closes_order_and_hazard_and_recalculates_project(monkeypatch):
    db = _session()
    _seed_base(db, status="waiting_review")
    calls = []

    def fake_recalculate(db_arg, request, current_user=None):
        calls.append((request.project_id, request.profile_types, current_user.user_id if current_user else None))
        return {"recalculated_projects": 1}

    monkeypatch.setattr("app.services.work_orders.workflow.profile_service.recalculate_profiles", fake_recalculate)

    result = transition_work_order(
        db,
        "WO-001",
        WorkOrderStatusUpdate(action="review_pass", comment="Accepted."),
        _user("gc_safety_officer", "U-GC-01"),
    )

    order = db.query(SafetyWorkOrder).filter_by(work_order_id="WO-001").one()
    hazard = db.query(Hazard).filter_by(hazard_id="H-001").one()
    flow = db.query(WorkOrderFlowLog).filter_by(action="review_pass").one()

    assert result["new_status"] == "closed"
    assert order.status == "closed"
    assert order.review_user_id == "U-GC-01"
    assert order.close_time is not None
    assert hazard.status == "closed"
    assert hazard.close_date == dt.date.today()
    assert flow.to_status == "closed"
    assert calls == [("P002", ["project"], "U-GC-01")]


def test_gc_review_reject_requires_reject_reason():
    db = _session()
    _seed_base(db, status="waiting_review")

    with pytest.raises(ValueError, match="Reject reason is required"):
        transition_work_order(
            db,
            "WO-001",
            WorkOrderStatusUpdate(action="review_reject"),
            _user("gc_safety_officer", "U-GC-01"),
        )
