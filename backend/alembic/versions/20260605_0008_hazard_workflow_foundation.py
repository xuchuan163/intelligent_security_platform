"""add hazard workflow foundation

Revision ID: 20260605_0008
Revises: 20260605_0007
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_0008"
down_revision = "20260605_0007"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _create_index_if_missing(inspector, table_name: str, index_name: str, columns: list[str]) -> None:
    if inspector.has_table(table_name) and not _has_index(inspector, table_name, index_name):
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("hazard"):
        for column in [
            sa.Column("discovered_by_user_id", sa.String(length=64), nullable=True),
            sa.Column("location", sa.String(length=255), nullable=True),
            sa.Column("attachments", sa.JSON(), nullable=True),
            sa.Column("work_order_id", sa.String(length=64), nullable=True),
        ]:
            if not _has_column(inspector, "hazard", column.name):
                op.add_column("hazard", column)
        inspector = sa.inspect(bind)
        _create_index_if_missing(inspector, "hazard", "ix_hazard_work_order_id", ["work_order_id"])

    if not inspector.has_table("project_user"):
        op.create_table(
            "project_user",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("org_path", sa.String(length=512), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("user_name", sa.String(length=128), nullable=False),
            sa.Column("role_code", sa.String(length=64), nullable=False),
            sa.Column("subcontractor_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "user_id", "role_code", name="uk_project_user_role"),
        )
    inspector = sa.inspect(bind)
    for index_name, columns in [
        ("ix_project_user_tenant_id", ["tenant_id"]),
        ("ix_project_user_company_id", ["company_id"]),
        ("ix_project_user_project_id", ["project_id"]),
        ("ix_project_user_user_id", ["user_id"]),
        ("ix_project_user_role_code", ["role_code"]),
        ("ix_project_user_subcontractor_id", ["subcontractor_id"]),
    ]:
        _create_index_if_missing(inspector, "project_user", index_name, columns)

    if not inspector.has_table("work_order_flow_log"):
        op.create_table(
            "work_order_flow_log",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("work_order_id", sa.String(length=64), nullable=False),
            sa.Column("from_status", sa.String(length=32), nullable=True),
            sa.Column("to_status", sa.String(length=32), nullable=False),
            sa.Column("action", sa.String(length=64), nullable=False),
            sa.Column("operator_user_id", sa.String(length=64), nullable=False),
            sa.Column("operator_role", sa.String(length=64), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("reject_reason", sa.Text(), nullable=True),
            sa.Column("attachments", sa.JSON(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    inspector = sa.inspect(bind)
    for index_name, columns in [
        ("ix_work_order_flow_log_work_order_id", ["work_order_id"]),
        ("ix_work_order_flow_log_action", ["action"]),
        ("ix_work_order_flow_log_operator_user_id", ["operator_user_id"]),
    ]:
        _create_index_if_missing(inspector, "work_order_flow_log", index_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("work_order_flow_log"):
        op.drop_table("work_order_flow_log")
    if inspector.has_table("project_user"):
        op.drop_table("project_user")

    if inspector.has_table("hazard"):
        for index_name in ["ix_hazard_work_order_id"]:
            if _has_index(inspector, "hazard", index_name):
                op.drop_index(index_name, table_name="hazard")
        for column_name in ["work_order_id", "attachments", "location", "discovered_by_user_id"]:
            if _has_column(inspector, "hazard", column_name):
                op.drop_column("hazard", column_name)
