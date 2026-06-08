"""add nl2sql execution result fields

Revision ID: 20260604_0006
Revises: 20260604_0005
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0006"
down_revision = "20260604_0005"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("agent_nl2sql_audit"):
        return
    if not _has_column(inspector, "agent_nl2sql_audit", "result_row_count"):
        op.add_column(
            "agent_nl2sql_audit",
            sa.Column("result_row_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column(inspector, "agent_nl2sql_audit", "result_field_count"):
        op.add_column(
            "agent_nl2sql_audit",
            sa.Column("result_field_count", sa.Integer(), nullable=False, server_default="0"),
        )
    if not _has_column(inspector, "agent_nl2sql_audit", "execution_error"):
        op.add_column("agent_nl2sql_audit", sa.Column("execution_error", sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("agent_nl2sql_audit"):
        return
    if _has_column(inspector, "agent_nl2sql_audit", "execution_error"):
        op.drop_column("agent_nl2sql_audit", "execution_error")
    if _has_column(inspector, "agent_nl2sql_audit", "result_field_count"):
        op.drop_column("agent_nl2sql_audit", "result_field_count")
    if _has_column(inspector, "agent_nl2sql_audit", "result_row_count"):
        op.drop_column("agent_nl2sql_audit", "result_row_count")
