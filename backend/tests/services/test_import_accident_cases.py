import textwrap
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base
from app.services.cases.import_cases import ImportCaseError, import_accident_cases_from_csv


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _write_csv(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "cases.csv"
    path.write_text(textwrap.dedent(content).strip() + "\n", encoding="utf-8")
    return path


def test_import_accident_cases_creates_rows_from_csv(tmp_path):
    csv_path = _write_csv(
        tmp_path,
        """
        accident_case_id,tenant_id,accident_type,severity,project_type,operation_scene,direct_cause,indirect_cause,involved_subjects,warning_indicators,rectification_measures,tags
        AC-IMPORT-101,TENANT-A,高处坠落,一般事故,housing,临边作业,防护缺失,交底不足,"{""subjects"":[""worker""]}","[{""metric_code"":""HAZARD_OVERDUE_COUNT"",""value"":1}]",恢复防护并复查,高处作业|临边防护
        """,
    )
    db = _session()

    result = import_accident_cases_from_csv(db, csv_path)

    assert result.created == 1
    assert result.updated == 0
    row = (
        db.query(AccidentCaseLibrary)
        .filter(AccidentCaseLibrary.accident_case_id == "AC-IMPORT-101")
        .one()
    )
    assert row.tenant_id == "TENANT-A"
    assert row.project_type == "housing"
    assert row.tags == ["高处作业", "临边防护"]
    assert row.status == "active"


def test_import_accident_cases_upserts_existing_row(tmp_path):
    csv_path = _write_csv(
        tmp_path,
        """
        accident_case_id,tenant_id,accident_type,severity,project_type,operation_scene,direct_cause,indirect_cause,involved_subjects,warning_indicators,rectification_measures,tags
        AC-IMPORT-102,TENANT-A,坍塌,一般事故,infrastructure,深基坑,支护失效,巡检不足,,,加固支护,坍塌
        AC-IMPORT-102,TENANT-A,坍塌,险情,infrastructure,深基坑,支护局部变形,巡检流于形式,,,立即加固并复测,坍塌|深基坑
        """,
    )
    db = _session()

    first = import_accident_cases_from_csv(db, csv_path)
    second = import_accident_cases_from_csv(db, csv_path)

    assert first.created == 1
    assert first.updated == 1
    assert second.created == 0
    assert second.updated == 2
    row = (
        db.query(AccidentCaseLibrary)
        .filter(AccidentCaseLibrary.accident_case_id == "AC-IMPORT-102")
        .one()
    )
    assert row.severity == "险情"
    assert row.tags == ["坍塌", "深基坑"]


def test_import_accident_cases_rejects_invalid_project_type(tmp_path):
    csv_path = _write_csv(
        tmp_path,
        """
        accident_case_id,tenant_id,accident_type,severity,project_type
        AC-IMPORT-103,TENANT-A,触电,一般事故,unknown_type
        """,
    )
    db = _session()

    try:
        import_accident_cases_from_csv(db, csv_path)
    except ImportCaseError as exc:
        assert "invalid project_type" in str(exc)
    else:
        raise AssertionError("expected ImportCaseError")


def test_import_accident_cases_dry_run_rolls_back(tmp_path):
    csv_path = _write_csv(
        tmp_path,
        """
        accident_case_id,tenant_id,accident_type,severity
        AC-IMPORT-104,TENANT-A,机械伤害,一般事故
        """,
    )
    db = _session()

    result = import_accident_cases_from_csv(db, csv_path, dry_run=True)

    assert result.created == 1
    assert db.query(AccidentCaseLibrary).count() == 0
