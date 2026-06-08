"""add phase 2 agent memory tables

Revision ID: 20260604_0003
Revises: 20260604_0002
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0003"
down_revision = "20260604_0002"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("agent_session_summary"):
        op.create_table(
            "agent_session_summary",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("org_path", sa.String(length=512), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("session_id", sa.String(length=64), nullable=False),
            sa.Column("summary", sa.Text(), nullable=True),
            sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_message_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_agent_session_summary_tenant_id", "agent_session_summary", ["tenant_id"])
        op.create_index("ix_agent_session_summary_org_path", "agent_session_summary", ["org_path"])
        op.create_index("ix_agent_session_summary_user_id", "agent_session_summary", ["user_id"])
        op.create_index("ix_agent_session_summary_session_id", "agent_session_summary", ["session_id"])
        op.create_index(
            "idx_agent_session_scope",
            "agent_session_summary",
            ["tenant_id", "user_id", "session_id"],
            unique=True,
        )

    if not inspector.has_table("agent_task_checkpoint"):
        op.create_table(
            "agent_task_checkpoint",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("org_path", sa.String(length=512), nullable=False),
            sa.Column("task_type", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=True),
            sa.Column("context_json", sa.JSON(), nullable=True),
            sa.Column("sub_task_json", sa.JSON(), nullable=True),
            sa.Column("result_ref", sa.String(length=255), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", name="uk_agent_task_checkpoint_task_id"),
        )
        op.create_index("ix_agent_task_checkpoint_tenant_id", "agent_task_checkpoint", ["tenant_id"])
        op.create_index("ix_agent_task_checkpoint_org_path", "agent_task_checkpoint", ["org_path"])
        op.create_index("ix_agent_task_checkpoint_user_id", "agent_task_checkpoint", ["user_id"])
    else:
        for column in (
            sa.Column("tenant_id", sa.String(length=64), nullable=False, server_default="CSCEC-DEMO"),
            sa.Column("org_path", sa.String(length=512), nullable=False, server_default="CSCEC-DEMO"),
        ):
            if not _has_column(inspector, "agent_task_checkpoint", column.name):
                op.add_column("agent_task_checkpoint", column)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("agent_task_checkpoint"):
        op.drop_table("agent_task_checkpoint")
    if inspector.has_table("agent_session_summary"):
        op.drop_index("idx_agent_session_scope", table_name="agent_session_summary")
        op.drop_index("ix_agent_session_summary_session_id", table_name="agent_session_summary")
        op.drop_index("ix_agent_session_summary_user_id", table_name="agent_session_summary")
        op.drop_index("ix_agent_session_summary_org_path", table_name="agent_session_summary")
        op.drop_index("ix_agent_session_summary_tenant_id", table_name="agent_session_summary")
        op.drop_table("agent_session_summary")
