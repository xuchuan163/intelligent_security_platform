"""add company project scope compatibility columns

Revision ID: 20260605_0007
Revises: 20260604_0006
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_0007"
down_revision = "20260604_0006"
branch_labels = None
depends_on = None


TENANT_SCOPED_TABLES = [
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
    "profile_calc_detail",
]

COMPANY_PROJECT_INDEXES = {
    "project": ("idx_project_company_project", ["company_id", "project_id"]),
    "worker": ("idx_worker_company_project", ["company_id", "project_id"]),
    "hazard": ("idx_hazard_company_project", ["company_id", "project_id"]),
    "equipment": ("idx_equipment_company_project", ["company_id", "project_id"]),
    "safety_work_order": ("idx_work_order_company_project", ["company_id", "project_id"]),
    "rule_trigger_log": ("idx_rule_trigger_company_project", ["company_id", "project_id"]),
    "metric_catalog": ("idx_metric_company_project", ["company_id", "project_id"]),
}


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _add_company_id_from_tenant(inspector, table_name: str) -> None:
    if not inspector.has_table(table_name) or _has_column(inspector, table_name, "company_id"):
        return
    op.add_column(table_name, sa.Column("company_id", sa.String(length=64), nullable=True))
    op.execute(sa.text(f"UPDATE {table_name} SET company_id = tenant_id"))
    op.alter_column(table_name, "company_id", existing_type=sa.String(length=64), nullable=False)


def _create_index_if_possible(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    if not inspector.has_table(table_name) or _has_index(inspector, table_name, index_name):
        return
    table_columns = {column["name"] for column in inspector.get_columns(table_name)}
    if set(columns) <= table_columns:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in TENANT_SCOPED_TABLES:
        _add_company_id_from_tenant(inspector, table_name)

    if inspector.has_table("metric_catalog"):
        if not _has_column(inspector, "metric_catalog", "company_id"):
            op.add_column(
                "metric_catalog",
                sa.Column("company_id", sa.String(length=64), nullable=False, server_default="CSCEC"),
            )
        if not _has_column(inspector, "metric_catalog", "project_id"):
            op.add_column("metric_catalog", sa.Column("project_id", sa.String(length=64), nullable=True))

    inspector = sa.inspect(bind)
    for table_name, (index_name, columns) in COMPANY_PROJECT_INDEXES.items():
        _create_index_if_possible(inspector, table_name, index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name, (index_name, _) in COMPANY_PROJECT_INDEXES.items():
        if inspector.has_table(table_name) and _has_index(inspector, table_name, index_name):
            op.drop_index(index_name, table_name=table_name)

    if inspector.has_table("metric_catalog"):
        if _has_column(inspector, "metric_catalog", "project_id"):
            op.drop_column("metric_catalog", "project_id")
        if _has_column(inspector, "metric_catalog", "company_id"):
            op.drop_column("metric_catalog", "company_id")

    for table_name in reversed(TENANT_SCOPED_TABLES):
        if inspector.has_table(table_name) and _has_column(inspector, table_name, "company_id"):
            op.drop_column(table_name, "company_id")
