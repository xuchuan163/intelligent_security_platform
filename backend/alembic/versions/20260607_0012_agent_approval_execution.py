"""add agent approval execution audit fields

Revision ID: 20260607_0012
Revises: 20260607_0011
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260607_0012"
down_revision = "20260607_0011"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "agent_approval_request"
    if not inspector.has_table(table_name):
        return

    for column in [
        sa.Column("executor_user_id", sa.String(length=64), nullable=True),
        sa.Column("executed_at", sa.DateTime(), nullable=True),
        sa.Column("execution_result", sa.JSON(), nullable=True),
        sa.Column("execution_error", sa.Text(), nullable=True),
    ]:
        if not _has_column(inspector, table_name, column.name):
            op.add_column(table_name, column)

    inspector = sa.inspect(bind)
    if not _has_index(inspector, table_name, "ix_agent_approval_request_executor_user_id"):
        op.create_index("ix_agent_approval_request_executor_user_id", table_name, ["executor_user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_name = "agent_approval_request"
    if not inspector.has_table(table_name):
        return
    if _has_index(inspector, table_name, "ix_agent_approval_request_executor_user_id"):
        op.drop_index("ix_agent_approval_request_executor_user_id", table_name=table_name)
    for column_name in ["execution_error", "execution_result", "executed_at", "executor_user_id"]:
        if _has_column(inspector, table_name, column_name):
            op.drop_column(table_name, column_name)
