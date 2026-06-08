from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser
from app.infrastructure.database.models import AgentNl2sqlAudit, Hazard, Project
from app.infrastructure.database.session import Base
from app.services.nl2sql.executor import execute_readonly_sql


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _tenant_user() -> MockUser:
    return MockUser(
        user_id="u-exec-001",
        user_name="Executor User",
        tenant_id="TENANT-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
    )


def test_executor_rejects_failed_audit_without_running_sql():
    db = _session()

    result = execute_readonly_sql(
        db,
        question="尝试删除项目",
        candidate_sql="delete from project where tenant_id = 'TENANT-A'",
        current_user=_tenant_user(),
    )

    assert result["allowed"] is False
    assert result["execution_status"] == "rejected"
    assert result["rows"] == []
    row = db.query(AgentNl2sqlAudit).one()
    assert row.execution_status == "rejected"
    assert row.result_row_count == 0
    assert row.result_field_count == 0
    assert row.execution_error is None


def test_executor_runs_only_sanitized_sql_and_returns_current_tenant_rows():
    db = _session()
    db.add_all(
        [
            Project(
                project_id="P-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01",
                project_name="In Scope",
                status="active",
            ),
            Project(
                project_id="P-OUT",
                tenant_id="TENANT-B",
                org_path="TENANT-B/BU-01",
                project_name="Out Scope",
                status="active",
            ),
        ]
    )
    db.commit()

    result = execute_readonly_sql(
        db,
        question="查询项目",
        candidate_sql="select project_id, project_name from project where status = 'active'",
        current_user=_tenant_user(),
    )

    assert result["allowed"] is True
    assert result["execution_status"] == "executed"
    assert result["row_count"] == 1
    assert result["columns"] == ["project_id", "project_name"]
    assert result["rows"] == [{"project_id": "P-IN", "project_name": "In Scope"}]
    assert "project.company_id = 'TENANT-A'" in result["sanitized_sql"]
    row = db.query(AgentNl2sqlAudit).one()
    assert row.execution_status == "executed"
    assert row.result_row_count == 1
    assert row.result_field_count == 2


def test_executor_caps_rows_fields_and_truncates_long_text():
    db = _session()
    db.add_all(
        [
            Project(
                project_id=f"P-{idx:03d}",
                tenant_id="TENANT-A",
                org_path="TENANT-A",
                project_name=f"Project {idx:03d}",
                status="active",
            )
            for idx in range(120)
        ]
    )
    db.add(
        Hazard(
            hazard_id="H-LONG",
            tenant_id="TENANT-A",
            org_path="TENANT-A",
            project_id="P-001",
            hazard_type="edge",
            hazard_level="general",
            description="x" * 800,
            status="open",
        )
    )
    db.commit()

    many_rows = execute_readonly_sql(
        db,
        question="查询很多项目",
        candidate_sql="select project_id, project_name from project limit 500",
        current_user=_tenant_user(),
    )
    many_fields = execute_readonly_sql(
        db,
        question="查询很多字段",
        candidate_sql=(
            "select "
            + ", ".join(f"project_id as c{i}" for i in range(31))
            + " from project limit 1"
        ),
        current_user=_tenant_user(),
    )
    long_text = execute_readonly_sql(
        db,
        question="查询长文本",
        candidate_sql="select hazard_id, description from hazard where hazard_id = 'H-LONG'",
        current_user=_tenant_user(),
    )

    assert many_rows["row_count"] == 100
    assert len(many_rows["rows"]) == 100
    assert many_fields["field_count"] == 30
    assert len(many_fields["columns"]) == 30
    assert len(long_text["rows"][0]["description"]) == 500


def test_executor_marks_failed_when_sanitized_sql_execution_errors():
    db = _session()
    db.add(
        Project(
            project_id="P-IN",
            tenant_id="TENANT-A",
            org_path="TENANT-A",
            project_name="In Scope",
            status="active",
        )
    )
    db.commit()

    result = execute_readonly_sql(
        db,
        question="触发执行异常",
        candidate_sql="select project_id from project where status = no_such_sql_func('active')",
        current_user=_tenant_user(),
    )

    assert result["allowed"] is True
    assert result["execution_status"] == "failed"
    assert result["rows"] == []
    assert result["execution_error"]
    row = db.query(AgentNl2sqlAudit).one()
    assert row.execution_status == "failed"
    assert row.execution_error
