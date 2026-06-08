"""add agent feedback table

Revision ID: 20260608_0013
Revises: 20260607_0012
Create Date: 2026-06-08
"""

from alembic import op
import sqlalchemy as sa


revision = "20260608_0013"
down_revision = "20260607_0012"
branch_labels = None
depends_on = None


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("agent_feedback"):
        op.create_table(
            "agent_feedback",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("feedback_id", sa.String(length=64), nullable=False),
            sa.Column("task_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("org_path", sa.String(length=512), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=True),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("agent_name", sa.String(length=64), nullable=False),
            sa.Column("feedback_type", sa.String(length=32), nullable=False),
            sa.Column("rating", sa.Integer(), nullable=True),
            sa.Column("feedback_reason", sa.String(length=255), nullable=True),
            sa.Column("original_output", sa.JSON(), nullable=True),
            sa.Column("corrected_output", sa.JSON(), nullable=True),
            sa.Column("correction_text", sa.Text(), nullable=True),
            sa.Column("related_work_order_id", sa.String(length=64), nullable=True),
            sa.Column("label_status", sa.String(length=32), nullable=False),
            sa.Column("used_for_prompt_tuning", sa.Boolean(), nullable=False),
            sa.Column("used_for_finetune", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("feedback_id", name="uk_agent_feedback_id"),
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("agent_feedback"):
        return

    for index_name, columns in [
        ("ix_agent_feedback_feedback_id", ["feedback_id"]),
        ("ix_agent_feedback_task_id", ["task_id"]),
        ("ix_agent_feedback_tenant_id", ["tenant_id"]),
        ("ix_agent_feedback_company_id", ["company_id"]),
        ("ix_agent_feedback_org_path", ["org_path"]),
        ("ix_agent_feedback_project_id", ["project_id"]),
        ("ix_agent_feedback_user_id", ["user_id"]),
        ("ix_agent_feedback_agent_name", ["agent_name"]),
        ("ix_agent_feedback_feedback_type", ["feedback_type"]),
        ("ix_agent_feedback_related_work_order_id", ["related_work_order_id"]),
        ("idx_agent_feedback_task", ["task_id"]),
        ("idx_agent_feedback_agent_time", ["agent_name", "created_at"]),
        ("idx_agent_feedback_company_project", ["company_id", "project_id"]),
    ]:
        if not _has_index(inspector, "agent_feedback", index_name):
            op.create_index(index_name, "agent_feedback", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("agent_feedback"):
        op.drop_table("agent_feedback")
