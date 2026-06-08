"""Scale data seeding tests (Phase 4-C.1)."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import (
    Project,
    ProjectRiskProfile,
    Subcontractor,
    SubcontractorRiskProfile,
    Tenant,
    Worker,
    WorkerRiskProfile,
)
from app.infrastructure.database.session import Base
from app.services.scale.seed_scale_data import ScaleSeedConfig, seed_scale_data


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_seed_scale_data_creates_requested_counts():
    db = _session()
    config = ScaleSeedConfig(
        tenant_id="TENANT-SCALE-A",
        project_count=5,
        subcontractors_per_project=2,
        workers_per_project=3,
        with_profiles=True,
    )

    result = seed_scale_data(db, config)

    assert result.projects_created == 5
    assert result.subcontractors_created == 10
    assert result.workers_created == 15
    assert result.project_profiles_upserted == 5
    assert result.worker_profiles_upserted == 15
    assert result.subcontractor_profiles_upserted == 10

    assert db.query(Tenant).filter_by(tenant_id="TENANT-SCALE-A").count() == 1
    assert db.query(Project).filter_by(tenant_id="TENANT-SCALE-A").count() == 5
    assert db.query(Subcontractor).filter_by(tenant_id="TENANT-SCALE-A").count() == 10
    assert db.query(Worker).filter_by(tenant_id="TENANT-SCALE-A").count() == 15
    assert db.query(ProjectRiskProfile).count() == 5


def test_seed_scale_data_is_idempotent():
    db = _session()
    config = ScaleSeedConfig(
        tenant_id="TENANT-SCALE-B",
        project_count=3,
        subcontractors_per_project=1,
        workers_per_project=2,
        with_profiles=False,
    )

    first = seed_scale_data(db, config)
    second = seed_scale_data(db, config)

    assert first.projects_created == 3
    assert first.workers_created == 6
    assert second.projects_created == 0
    assert second.projects_updated == 3
    assert second.workers_created == 0
    assert second.workers_updated == 6
    assert db.query(Project).filter_by(tenant_id="TENANT-SCALE-B").count() == 3


def test_seed_scale_data_keeps_demo_tenant_isolated():
    db = _session()
    db.add(Tenant(tenant_id="CSCEC", tenant_name="Demo Tenant", status="active"))
    db.add(
        Project(
            project_id="P001",
            tenant_id="CSCEC",
            company_id="CSCEC",
            org_path="CSCEC/P001",
            project_name="演示项目",
            project_type="housing",
            status="active",
        )
    )
    db.commit()

    seed_scale_data(
        db,
        ScaleSeedConfig(
            tenant_id="TENANT-SCALE-C",
            project_count=2,
            subcontractors_per_project=1,
            workers_per_project=1,
            with_profiles=True,
        ),
    )

    assert db.query(Project).filter_by(tenant_id="CSCEC").count() == 1
    assert db.query(Project).filter_by(tenant_id="TENANT-SCALE-C").count() == 2
    assert db.query(WorkerRiskProfile).count() == 2
    assert db.query(SubcontractorRiskProfile).count() == 2


def test_seed_scale_data_profiles_idempotent_with_multiple_subcontractors():
    db = _session()
    config = ScaleSeedConfig(
        tenant_id="TENANT-SCALE-D",
        project_count=2,
        subcontractors_per_project=2,
        workers_per_project=2,
        with_profiles=True,
        id_prefix="IDEM",
    )

    first = seed_scale_data(db, config)
    second = seed_scale_data(db, config)

    assert first.subcontractor_profiles_upserted == 4
    assert second.subcontractor_profiles_upserted == 4
    assert db.query(SubcontractorRiskProfile).count() == 4
