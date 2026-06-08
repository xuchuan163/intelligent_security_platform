import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import RuleTriggerLog
from app.infrastructure.database.session import Base
from app.services.rules.service import list_rule_triggers


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _seed_triggers(db) -> None:
    now = dt.datetime.utcnow()
    db.add_all(
        [
            RuleTriggerLog(
                rule_id="SR-PROJ-001",
                tenant_id="CSCEC",
                org_path="CSCEC/P001",
                object_type="project",
                object_id="P001",
                project_id="P001",
                trigger_condition="major overdue",
                severity="critical",
                created_at=now,
            ),
            RuleTriggerLog(
                rule_id="SR-PROJ-004",
                tenant_id="CSCEC",
                org_path="CSCEC/P002",
                object_type="project",
                object_id="P002",
                project_id="P002",
                trigger_condition="equipment overdue",
                severity="high",
                created_at=now + dt.timedelta(seconds=1),
            ),
            RuleTriggerLog(
                rule_id="SR-WORKER-001",
                tenant_id="CSCEC",
                org_path="CSCEC/P001",
                object_type="worker",
                object_id="W001",
                project_id="P001",
                trigger_condition="cert expired",
                severity="high",
                created_at=now + dt.timedelta(seconds=2),
            ),
        ]
    )
    db.commit()


def test_list_rule_triggers_filters_by_project_id():
    db = _session()
    _seed_triggers(db)

    rows = list_rule_triggers(db, project_id="P001")

    assert len(rows) == 2
    assert {row["project_id"] for row in rows} == {"P001"}


def test_list_rule_triggers_filters_by_rule_id():
    db = _session()
    _seed_triggers(db)

    rows = list_rule_triggers(db, rule_id="SR-PROJ-004")

    assert len(rows) == 1
    assert rows[0]["rule_id"] == "SR-PROJ-004"
    assert rows[0]["project_id"] == "P002"


def test_list_rule_triggers_filters_by_project_and_rule_id():
    db = _session()
    _seed_triggers(db)

    rows = list_rule_triggers(db, project_id="P001", rule_id="SR-WORKER-001")

    assert len(rows) == 1
    assert rows[0]["object_id"] == "W001"
