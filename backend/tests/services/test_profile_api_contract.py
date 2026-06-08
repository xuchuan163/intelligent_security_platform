import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import (
    Project,
    ProjectRiskProfile,
    Subcontractor,
    SubcontractorRiskProfile,
    Worker,
    WorkerRiskProfile,
)
from app.infrastructure.database.session import Base
from app.services.profiles.service import (
    get_project_profile,
    get_subcontractor_profile,
    get_worker_profile,
)


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_project_profile_includes_calculated_at_and_confidence_level():
    db = _session()
    calc_date = dt.date(2026, 6, 4)
    db.add(
        Project(
            project_id="P-CONTRACT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-CONTRACT",
            project_name="Contract Project",
        )
    )
    db.add(
        ProjectRiskProfile(
            project_id="P-CONTRACT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-CONTRACT",
            calc_date=calc_date,
            total_risk_score=72,
            risk_level="high",
            confidence_level="medium_high",
        )
    )
    db.commit()

    data = get_project_profile(db, "P-CONTRACT")

    assert data is not None
    assert data["calculated_at"] == "2026-06-04"
    assert data["confidence_level"] == "medium_high"


def test_worker_profile_includes_calculated_at_and_confidence_level():
    db = _session()
    calc_date = dt.date(2026, 6, 4)
    db.add(
        Worker(
            worker_id="W-CONTRACT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-CONTRACT",
            project_id="P-CONTRACT",
            worker_name_masked="W**",
        )
    )
    db.add(
        WorkerRiskProfile(
            worker_id="W-CONTRACT",
            project_id="P-CONTRACT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-CONTRACT",
            calc_date=calc_date,
            total_risk_score=64,
            risk_level="high",
            confidence_level="medium",
        )
    )
    db.commit()

    data = get_worker_profile(db, "W-CONTRACT")

    assert data is not None
    assert data["calculated_at"] == "2026-06-04"
    assert data["confidence_level"] == "medium"


def test_subcontractor_profile_includes_calculated_at_and_confidence_level():
    db = _session()
    calc_date = dt.date(2026, 6, 4)
    db.add(
        Subcontractor(
            subcontractor_id="S-CONTRACT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-CONTRACT",
            subcontractor_name="Contract Sub",
        )
    )
    db.add(
        SubcontractorRiskProfile(
            subcontractor_id="S-CONTRACT",
            project_id="P-CONTRACT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-CONTRACT",
            calc_date=calc_date,
            total_risk_score=61,
            risk_level="high",
            confidence_level="medium",
        )
    )
    db.commit()

    data = get_subcontractor_profile(db, "S-CONTRACT")

    assert data is not None
    assert data["calculated_at"] == "2026-06-04"
    assert data["confidence_level"] == "medium"
