import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser
from app.infrastructure.database.models import (
    Hazard,
    Project,
    RuleTriggerLog,
    SafetyWorkOrder,
    Subcontractor,
    SubcontractorRiskProfile,
    Worker,
    WorkerRiskProfile,
)
from app.infrastructure.database.session import Base
from app.schemas.profiles import ProfileRecalculateRequest
from app.services.profiles.service import recalculate_profiles


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _user(org_path: str = "TENANT-A/BU-01") -> MockUser:
    return MockUser(
        user_id="u-safety-001",
        user_name="Safety Manager",
        tenant_id="TENANT-A",
        org_path=org_path,
        role="safety_manager",
        data_scope=DataScope.ORG,
    )


def _seed_worker_and_subcontractor(db):
    today = dt.date.today()
    db.add(
        Project(
            project_id="P-TC",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-TC",
            project_name="Task C Test Project",
            status="active",
            schedule_pressure_index=5,
        )
    )
    db.add(
        Subcontractor(
            subcontractor_id="SUB-TC",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-TC",
            subcontractor_name="Task C Subcontractor",
            safety_license_status="expired",
            accident_history_count=1,
            status="active",
        )
    )
    db.add(
        Worker(
            worker_id="W-TC",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-TC",
            project_id="P-TC",
            subcontractor_id="SUB-TC",
            worker_name_masked="王*",
            exam_score=55,
            violation_count_30d=3,
            special_cert_status="expired",
            health_check_status="valid",
            entry_days=30,
            status="active",
        )
    )
    db.add(
        Hazard(
            hazard_id="HZ-TC",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-TC",
            project_id="P-TC",
            subcontractor_id="SUB-TC",
            hazard_type="major",
            hazard_level="major",
            description="Subcontractor overdue major hazard",
            status="open",
            due_date=today - dt.timedelta(days=1),
            is_major=True,
        )
    )
    db.commit()


def test_recalculate_profiles_creates_worker_and_subcontractor_profiles():
    db = _session()
    _seed_worker_and_subcontractor(db)

    result = recalculate_profiles(
        db,
        ProfileRecalculateRequest(profile_types=["worker", "subcontractor"]),
        current_user=_user(),
    )

    worker_profile = db.query(WorkerRiskProfile).filter(WorkerRiskProfile.worker_id == "W-TC").one()
    sub_profile = db.query(SubcontractorRiskProfile).filter(
        SubcontractorRiskProfile.subcontractor_id == "SUB-TC"
    ).one()
    rule_ids = [row.rule_id for row in db.query(RuleTriggerLog).order_by(RuleTriggerLog.rule_id).all()]

    assert result["recalculated_projects"] == 0
    assert result["recalculated_workers"] == 1
    assert result["recalculated_subcontractors"] == 1
    assert result["created_work_orders"] == 4
    assert result["skipped_duplicate_work_orders"] == 0
    assert worker_profile.risk_level == "high"
    assert "rule:SR-WORKER-001" in worker_profile.strong_rule_flags["evidence"]
    assert sub_profile.risk_level in {"high", "critical"}
    assert sub_profile.high_risk_worker_ratio == 1.0
    assert {"SR-WORKER-001", "SR-WORKER-005", "SR-SUB-001", "SR-SUB-004"} <= set(rule_ids)
    work_order_rule_ids = {
        row.rule_id for row in db.query(SafetyWorkOrder).order_by(SafetyWorkOrder.rule_id).all()
    }
    assert {"SR-WORKER-001", "SR-WORKER-005", "SR-SUB-001", "SR-SUB-004"} <= work_order_rule_ids


def test_recalculate_profiles_respects_current_user_org_scope():
    db = _session()
    _seed_worker_and_subcontractor(db)
    db.add(
        Worker(
            worker_id="W-OUT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-02/P-OUT",
            project_id="P-OUT",
            subcontractor_id="SUB-OUT",
            worker_name_masked="李*",
            violation_count_30d=3,
            special_cert_status="expired",
            health_check_status="valid",
            entry_days=30,
            status="active",
        )
    )
    db.commit()

    result = recalculate_profiles(
        db,
        ProfileRecalculateRequest(profile_types=["worker"]),
        current_user=_user("TENANT-A/BU-01"),
    )

    worker_ids = [row.worker_id for row in db.query(WorkerRiskProfile).order_by(WorkerRiskProfile.worker_id).all()]
    assert result["recalculated_workers"] == 1
    assert worker_ids == ["W-TC"]
