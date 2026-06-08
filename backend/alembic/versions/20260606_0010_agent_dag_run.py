"""add controlled agent dag audit tables

Revision ID: 20260606_0010
Revises: 20260605_0009
Create Date: 2026-06-06
"""

from alembic import op
import sqlalchemy as sa


revision = "20260606_0010"
down_revision = "20260605_0009"
branch_labels = None
depends_on = None


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("agent_dag_run"):
        op.create_table(
            "agent_dag_run",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=True),
            sa.Column("scope_type", sa.String(length=32), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("execution_mode", sa.String(length=32), nullable=False),
            sa.Column("target_agent", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("need_human_review", sa.Boolean(), nullable=False),
            sa.Column("blocked_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("run_id", name="uk_agent_dag_run_id"),
        )

    if not inspector.has_table("agent_dag_step_run"):
        op.create_table(
            "agent_dag_step_run",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("step_run_id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("step_id", sa.String(length=64), nullable=False),
            sa.Column("agent_code", sa.String(length=64), nullable=False),
            sa.Column("action", sa.String(length=128), nullable=False),
            sa.Column("tool_name", sa.String(length=128), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("will_execute", sa.Boolean(), nullable=False),
            sa.Column("requires_human_review", sa.Boolean(), nullable=False),
            sa.Column("input_summary", sa.JSON(), nullable=True),
            sa.Column("output_summary", sa.JSON(), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("elapsed_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("step_run_id", name="uk_agent_dag_step_run_id"),
        )

    inspector = sa.inspect(bind)
    for table_name, indexes in {
        "agent_dag_run": [
            ("ix_agent_dag_run_run_id", ["run_id"]),
            ("ix_agent_dag_run_tenant_id", ["tenant_id"]),
            ("ix_agent_dag_run_company_id", ["company_id"]),
            ("ix_agent_dag_run_project_id", ["project_id"]),
            ("ix_agent_dag_run_user_id", ["user_id"]),
            ("ix_agent_dag_run_status", ["status"]),
            ("idx_agent_dag_run_company_project", ["company_id", "project_id"]),
            ("idx_agent_dag_run_user_created", ["user_id", "created_at"]),
        ],
        "agent_dag_step_run": [
            ("ix_agent_dag_step_run_step_run_id", ["step_run_id"]),
            ("ix_agent_dag_step_run_run_id", ["run_id"]),
            ("ix_agent_dag_step_run_tool_name", ["tool_name"]),
            ("ix_agent_dag_step_run_status", ["status"]),
            ("idx_agent_dag_step_run_run", ["run_id"]),
        ],
    }.items():
        if not inspector.has_table(table_name):
            continue
        for index_name, columns in indexes:
            if not _has_index(inspector, table_name, index_name):
                op.create_index(index_name, table_name, columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("agent_dag_step_run"):
        op.drop_table("agent_dag_step_run")
    if inspector.has_table("agent_dag_run"):
        op.drop_table("agent_dag_run")
