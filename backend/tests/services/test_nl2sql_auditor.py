import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import AgentNl2sqlAudit
from app.infrastructure.database.session import Base
from app.services.nl2sql.auditor import audit_sql, audit_sql_with_log


DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "nl2sql_audit_cases.jsonl"


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _tenant_user() -> MockUser:
    return MockUser(
        user_id="u-nl2sql-001",
        user_name="NL2SQL User",
        tenant_id="TENANT-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
    )


def _company_user() -> MockUser:
    return MockUser(
        user_id="u-nl2sql-company-001",
        user_name="Company User",
        tenant_id="TENANT-A",
        company_id="COMPANY-A",
        org_path="TENANT-A",
        role="company_admin",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def _org_user() -> MockUser:
    return MockUser(
        user_id="u-nl2sql-002",
        user_name="Org User",
        tenant_id="TENANT-A",
        org_path="TENANT-A/BU-01",
        role="safety_manager",
        data_scope=DataScope.ORG,
    )


def _project_scope_user() -> MockUser:
    return MockUser(
        user_id="u-nl2sql-003",
        user_name="Project User",
        tenant_id="TENANT-A",
        company_id="COMPANY-A",
        org_path="TENANT-A/legacy",
        role="project_manager",
        data_scope=DataScope.ORG,
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P001", "P002"),
    )


def test_nl2sql_audit_dataset_has_30_security_cases():
    cases = [json.loads(line) for line in DATASET_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    categories = {case["category"] for case in cases}

    assert len(cases) >= 30
    assert {
        "allow_select",
        "add_limit",
        "reject_write",
        "reject_multi_statement",
        "reject_select_star",
        "reject_table",
        "reject_field",
        "reject_tenant_override",
        "inject_org_scope",
    } <= categories


def test_audit_allows_single_table_select_and_injects_tenant_and_limit():
    result = audit_sql(
        "select project_id, project_name from project where status = 'active'",
        current_user=_company_user(),
    )

    assert result.allowed is True
    assert result.scope_injected is True
    assert result.reject_reason is None
    assert result.tables_used == ["project"]
    assert result.fields_used == ["project_id", "project_name", "status"]
    assert "project.company_id = 'COMPANY-A'" in result.sanitized_sql
    assert "tenant_id" not in result.sanitized_sql
    assert "org_path" not in result.sanitized_sql
    assert "LIMIT 100" in result.sanitized_sql


def test_audit_rejects_write_multi_statement_star_blocked_table_and_field():
    user = _tenant_user()

    cases = [
        ("delete from project where tenant_id='TENANT-A'", "only SELECT statements are allowed"),
        ("select project_id from project; select worker_id from worker", "multiple SQL statements are not allowed"),
        ("select * from worker", "SELECT * is not allowed"),
        ("select session_id from agent_session_summary", "table not allowed: agent_session_summary"),
        ("select identity_card from worker", "field not allowed: worker.identity_card"),
    ]

    for sql, reason in cases:
        result = audit_sql(sql, current_user=user)
        assert result.allowed is False
        assert result.sanitized_sql is None
        assert result.reject_reason == reason


def test_audit_rejects_tenant_override_and_injects_org_scope():
    tenant_override = audit_sql(
        "select project_id from project where tenant_id = 'TENANT-B'",
        current_user=_tenant_user(),
    )
    org_scoped = audit_sql(
        "select worker_id, worker_name_masked from worker where status = 'active' limit 20",
        current_user=_org_user(),
    )

    assert tenant_override.allowed is False
    assert tenant_override.reject_reason == "tenant_id override is not allowed"
    assert org_scoped.allowed is True
    assert "worker.company_id = 'TENANT-A'" in org_scoped.sanitized_sql
    assert "org_path LIKE 'TENANT-A/BU-01%'" in org_scoped.sanitized_sql
    assert "LIMIT 20" in org_scoped.sanitized_sql


def test_audit_rejects_company_id_override():
    result = audit_sql(
        "select project_id from project where company_id = 'COMPANY-B'",
        current_user=_company_user(),
    )

    assert result.allowed is False
    assert result.reject_reason == "company_id override is not allowed"


def test_audit_project_scope_injects_authorized_project_ids_before_org_path():
    result = audit_sql(
        "select project_id, project_name from project where status = 'active'",
        current_user=_project_scope_user(),
    )

    assert result.allowed is True
    assert "project.company_id = 'COMPANY-A'" in result.sanitized_sql
    assert "project.project_id IN ('P001', 'P002')" in result.sanitized_sql
    assert "tenant_id" not in result.sanitized_sql
    assert "org_path LIKE" not in result.sanitized_sql
    assert "LIMIT 100" in result.sanitized_sql


def test_audit_project_scope_keeps_company_metric_defaults_visible():
    result = audit_sql(
        "select metric_code, metric_name from metric_catalog where status = 'enabled'",
        current_user=_project_scope_user(),
    )

    assert result.allowed is True
    assert "metric_catalog.company_id = 'COMPANY-A'" in result.sanitized_sql
    assert "metric_catalog.project_id IS NULL" in result.sanitized_sql
    assert "metric_catalog.project_id IN ('P001', 'P002')" in result.sanitized_sql
    assert "tenant_id" not in result.sanitized_sql
    assert "LIMIT 100" in result.sanitized_sql


def test_audit_project_scope_rejects_project_id_override():
    result = audit_sql(
        "select project_id, project_name from project where project_id = 'P999'",
        current_user=_project_scope_user(),
    )

    assert result.allowed is False
    assert result.reject_reason == "project_id override is not allowed"


def test_audit_handles_table_alias_scope_and_rejects_ambiguous_join_columns():
    allowed_join = audit_sql(
        (
            "select p.project_id, h.hazard_id from project p "
            "join hazard h on p.project_id = h.project_id where h.status = 'open'"
        ),
        current_user=_org_user(),
    )
    ambiguous_join = audit_sql(
        "select project_id from project p join hazard h on p.project_id = h.project_id",
        current_user=_tenant_user(),
    )

    assert allowed_join.allowed is True
    assert "p.company_id = 'TENANT-A'" in allowed_join.sanitized_sql
    assert "h.company_id = 'TENANT-A'" in allowed_join.sanitized_sql
    assert "p.org_path LIKE 'TENANT-A/BU-01%'" in allowed_join.sanitized_sql
    assert "h.org_path LIKE 'TENANT-A/BU-01%'" in allowed_join.sanitized_sql
    assert "LIMIT 100" in allowed_join.sanitized_sql
    assert ambiguous_join.allowed is False
    assert ambiguous_join.reject_reason == "ambiguous unqualified field in multi-table query: project_id"


def test_audit_caps_limit_and_logs_result_to_mysql():
    db = _session()

    result = audit_sql_with_log(
        db,
        question="列出高风险项目",
        candidate_sql="select project_id, risk_level from project_risk_profile where risk_level = 'high' limit 2000",
        current_user=_tenant_user(),
    )

    assert result.allowed is True
    assert "LIMIT 500" in result.sanitized_sql

    row = db.query(AgentNl2sqlAudit).one()
    assert row.tenant_id == "TENANT-A"
    assert row.user_id == "u-nl2sql-001"
    assert row.question == "列出高风险项目"
    assert row.candidate_sql.startswith("select project_id")
    assert row.allowed is True
    assert row.scope_injected is True
    assert row.execution_status == "audited"
    assert row.tables_used == ["project_risk_profile"]
    assert row.fields_used == ["project_id", "risk_level"]
