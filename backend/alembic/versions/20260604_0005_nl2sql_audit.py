"""add nl2sql audit table

Revision ID: 20260604_0005
Revises: 20260604_0004
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0005"
down_revision = "20260604_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("agent_nl2sql_audit"):
        return

    op.create_table(
        "agent_nl2sql_audit",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("audit_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("org_path", sa.String(length=512), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("candidate_sql", sa.Text(), nullable=False),
        sa.Column("sanitized_sql", sa.Text(), nullable=True),
        sa.Column("allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reject_reason", sa.Text(), nullable=True),
        sa.Column("tables_used", sa.JSON(), nullable=True),
        sa.Column("fields_used", sa.JSON(), nullable=True),
        sa.Column("scope_injected", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("execution_status", sa.String(length=32), nullable=False, server_default="audited"),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_id", name="uk_agent_nl2sql_audit_id"),
    )
    op.create_index("ix_agent_nl2sql_audit_audit_id", "agent_nl2sql_audit", ["audit_id"])
    op.create_index("ix_agent_nl2sql_audit_tenant_id", "agent_nl2sql_audit", ["tenant_id"])
    op.create_index("ix_agent_nl2sql_audit_org_path", "agent_nl2sql_audit", ["org_path"])
    op.create_index("ix_agent_nl2sql_audit_user_id", "agent_nl2sql_audit", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("agent_nl2sql_audit"):
        return
    op.drop_index("ix_agent_nl2sql_audit_user_id", table_name="agent_nl2sql_audit")
    op.drop_index("ix_agent_nl2sql_audit_org_path", table_name="agent_nl2sql_audit")
    op.drop_index("ix_agent_nl2sql_audit_tenant_id", table_name="agent_nl2sql_audit")
    op.drop_index("ix_agent_nl2sql_audit_audit_id", table_name="agent_nl2sql_audit")
    op.drop_table("agent_nl2sql_audit")
