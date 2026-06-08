from app.infrastructure.database import models  # noqa: F401
from app.infrastructure.database.session import Base


TENANT_SCOPED_TABLES_REQUIRING_COMPANY_ID = {
    "project",
    "subcontractor",
    "worker",
    "hazard",
    "equipment",
    "project_risk_profile",
    "worker_risk_profile",
    "subcontractor_risk_profile",
    "rule_trigger_log",
    "safety_work_order",
    "agent_task_log",
    "agent_nl2sql_audit",
    "accident_case_library",
    "agent_session_summary",
    "agent_task_checkpoint",
    "agent_approval_request",
    "profile_calc_detail",
}

PROJECT_SCOPED_TABLES_REQUIRING_PROJECT_ID = {
    "project",
    "worker",
    "hazard",
    "equipment",
    "project_risk_profile",
    "worker_risk_profile",
    "subcontractor_risk_profile",
    "rule_trigger_log",
    "safety_work_order",
    "profile_calc_detail",
}


def test_tenant_scoped_tables_have_company_id_for_compatibility_migration():
    for table_name in TENANT_SCOPED_TABLES_REQUIRING_COMPANY_ID:
        table = Base.metadata.tables[table_name]

        assert "tenant_id" in table.columns
        assert "company_id" in table.columns, table_name
        assert table.columns["company_id"].nullable is False


def test_project_scoped_tables_keep_project_id_boundary():
    for table_name in PROJECT_SCOPED_TABLES_REQUIRING_PROJECT_ID:
        table = Base.metadata.tables[table_name]

        assert "project_id" in table.columns, table_name


def test_metric_catalog_supports_company_level_and_project_override_config():
    table = Base.metadata.tables["metric_catalog"]

    assert "company_id" in table.columns
    assert table.columns["company_id"].nullable is False
    assert "project_id" in table.columns
    assert table.columns["project_id"].nullable is True
