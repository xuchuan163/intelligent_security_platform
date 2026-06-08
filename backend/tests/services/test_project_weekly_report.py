import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import (
    Hazard,
    Project,
    ProjectRiskProfile,
    RuleTriggerLog,
    SafetyWorkOrder,
)
from app.infrastructure.database.session import Base
from app.services.reports.service import get_project_weekly_report

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


def _seed_project_bundle(db) -> None:
    db.add(
        Project(
            project_id="P001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P001",
            project_name="上海临港TOD综合开发项目",
            project_type="housing",
            status="active",
        )
    )
    db.add(
        ProjectRiskProfile(
            project_id="P001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P001",
            calc_date=TODAY,
            total_risk_score=68.0,
            risk_level="high",
            data_completeness=0.9,
        )
    )
    db.add(
        Hazard(
            hazard_id="H001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P001",
            project_id="P001",
            hazard_type="脚手架",
            hazard_level="major",
            description="外架连墙件不足",
            status="open",
            due_date=TODAY - dt.timedelta(days=2),
            is_major=True,
        )
    )
    db.add(
        RuleTriggerLog(
            rule_id="SR-PROJ-001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P001",
            object_type="project",
            object_id="P001",
            project_id="P001",
            trigger_condition="major_hazard_overdue_count=1",
            evidence={"count": 1},
            severity="high",
            created_at=dt.datetime.combine(TODAY, dt.time(hour=10)),
        )
    )
    db.add(
        SafetyWorkOrder(
            work_order_id="WO001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P001",
            work_order_type="rectification",
            project_id="P001",
            title="外架连墙件加固整改",
            description="H001 整改",
            status="dispatched",
            priority="high",
            rule_id="SR-PROJ-001",
            created_at=dt.datetime.combine(TODAY, dt.time(hour=11)),
        )
    )
    db.commit()


def test_get_project_weekly_report_returns_kpi_rules_and_work_orders():
    db = _session()
    _seed_project_bundle(db)

    report = get_project_weekly_report(db, "P001", week_end=TODAY)

    assert report is not None
    assert report["report_type"] == "project_weekly"
    assert report["project_id"] == "P001"
    assert report["kpi"]["risk_level"] == "high"
    assert report["kpi"]["overdue_hazards"] == 1
    assert report["kpi"]["rule_triggers_count"] == 1
    assert report["kpi"]["open_work_orders"] == 1
    assert len(report["rule_triggers"]) == 1
    assert report["rule_triggers"][0]["rule_id"] == "SR-PROJ-001"
    assert len(report["work_orders"]) == 1
    assert report["work_orders"][0]["work_order_id"] == "WO001"
    assert report["highlights"]
    assert report["evidence_refs"]


def test_get_project_weekly_report_returns_none_for_missing_project():
    db = _session()
    assert get_project_weekly_report(db, "P404", week_end=TODAY) is None
