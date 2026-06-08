import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import (
    Hazard,
    Project,
    SafetyWorkOrder,
    Subcontractor,
    SubcontractorRiskProfile,
    Worker,
    WorkerRiskProfile,
)
from app.infrastructure.database.session import Base
from app.services.reports.service import get_subcontractor_eval_report

TODAY = dt.date(2026, 6, 3)


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _seed_subcontractor_bundle(db) -> None:
    db.add(
        Project(
            project_id="P002",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P002",
            project_name="武汉长江中心",
            status="active",
        )
    )
    db.add(
        Subcontractor(
            subcontractor_id="S003",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P002/S003",
            subcontractor_name="广东宏大建设有限公司",
            qualification="二级",
            safety_license_status="valid",
            accident_history_count=2,
            credit_score=60.0,
            status="active",
        )
    )
    db.add(
        SubcontractorRiskProfile(
            subcontractor_id="S003",
            project_id="P002",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P002/S003",
            calc_date=TODAY,
            total_risk_score=72.0,
            risk_level="high",
            data_completeness=0.88,
            high_risk_worker_ratio=0.5,
            overdue_rectification_ratio=0.5,
            explanation="分包商广东宏大建设有限公司风险等级high",
        )
    )
    db.add(
        Worker(
            worker_id="W005",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P002/S003",
            project_id="P002",
            subcontractor_id="S003",
            worker_name_masked="刘**",
            work_type="普工",
            violation_count_30d=4,
            status="active",
        )
    )
    db.add(
        WorkerRiskProfile(
            worker_id="W005",
            project_id="P002",
            subcontractor_id="S003",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P002/S003",
            calc_date=TODAY,
            total_risk_score=78.0,
            risk_level="high",
        )
    )
    db.add(
        Hazard(
            hazard_id="H005",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P002",
            project_id="P002",
            subcontractor_id="S003",
            hazard_type="基坑",
            hazard_level="major",
            description="基坑边坡局部开裂",
            status="open",
            due_date=TODAY - dt.timedelta(days=1),
            is_major=True,
        )
    )
    db.add(
        SafetyWorkOrder(
            work_order_id="WO004",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P002",
            work_order_type="rectification",
            project_id="P002",
            subcontractor_id="S003",
            title="基坑边坡加固整改",
            status="processing",
            priority="critical",
            rule_id="SR-PROJ-001",
        )
    )
    db.commit()


def test_get_subcontractor_eval_report_returns_profile_kpi_and_actions():
    db = _session()
    _seed_subcontractor_bundle(db)

    report = get_subcontractor_eval_report(db, "S003", eval_date=TODAY)

    assert report is not None
    assert report["report_type"] == "subcontractor_eval"
    assert report["subcontractor_id"] == "S003"
    assert report["profile"]["eval_grade"] == "预警"
    assert report["kpi"]["overdue_hazards"] == 1
    assert report["kpi"]["high_risk_workers"] == 1
    assert report["kpi"]["violations_30d"] == 4
    assert report["kpi"]["accident_history_count"] == 2
    assert len(report["hazards"]) == 1
    assert len(report["work_orders"]) == 1
    assert report["highlights"]
    assert report["recommendations"]
    assert report["evidence_refs"]


def test_get_subcontractor_eval_report_returns_none_for_missing_subcontractor():
    db = _session()
    assert get_subcontractor_eval_report(db, "S404", eval_date=TODAY) is None
