import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import Hazard, Project, RuleTriggerLog
from app.infrastructure.database.session import Base
from app.services.profiles.service import recalculate_project_profiles


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_project_recalculate_writes_rule_trigger_logs():
    db = _session()
    today = dt.date.today()
    db.add(
        Project(
            project_id="P-RULE",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-RULE",
            project_name="规则测试项目",
            status="active",
            schedule_pressure_index=5,
        )
    )
    db.add(
        Hazard(
            hazard_id="HZ-RULE-001",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01/P-RULE",
            project_id="P-RULE",
            hazard_type="major",
            hazard_level="major",
            description="重大隐患超期未闭环",
            status="open",
            due_date=today - dt.timedelta(days=1),
            is_major=True,
        )
    )
    db.commit()

    result = recalculate_project_profiles(db)

    logs = db.query(RuleTriggerLog).all()
    assert result["recalculated_projects"] == 1
    assert result["created_work_orders"] == 1
    assert [log.rule_id for log in logs] == ["SR-PROJ-001"]
    assert logs[0].object_type == "project"
    assert logs[0].object_id == "P-RULE"
    assert logs[0].evidence["rule_name"] == "重大隐患超期未闭环"
