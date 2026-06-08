"""add agent approval request queue

Revision ID: 20260607_0011
Revises: 20260606_0010
Create Date: 2026-06-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260607_0011"
down_revision = "20260606_0010"
branch_labels = None
depends_on = None


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("agent_approval_request"):
        op.create_table(
            "agent_approval_request",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("approval_id", sa.String(length=64), nullable=False),
            sa.Column("run_id", sa.String(length=64), nullable=False),
            sa.Column("step_run_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=True),
            sa.Column("scope_type", sa.String(length=32), nullable=False),
            sa.Column("request_user_id", sa.String(length=64), nullable=False),
            sa.Column("requested_tool", sa.String(length=128), nullable=False),
            sa.Column("requested_action", sa.String(length=128), nullable=False),
            sa.Column("target_type", sa.String(length=64), nullable=False),
            sa.Column("target_id", sa.String(length=128), nullable=True),
            sa.Column("payload_summary", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=True),
            sa.Column("risk_level", sa.String(length=32), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("evidence_refs", sa.JSON(), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("approver_user_id", sa.String(length=64), nullable=True),
            sa.Column("approval_comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("rejected_at", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("approval_id", name="uk_agent_approval_request_id"),
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("agent_approval_request"):
        return

    for index_name, columns in [
        ("ix_agent_approval_request_approval_id", ["approval_id"]),
        ("ix_agent_approval_request_run_id", ["run_id"]),
        ("ix_agent_approval_request_step_run_id", ["step_run_id"]),
        ("ix_agent_approval_request_tenant_id", ["tenant_id"]),
        ("ix_agent_approval_request_company_id", ["company_id"]),
        ("ix_agent_approval_request_project_id", ["project_id"]),
        ("ix_agent_approval_request_request_user_id", ["request_user_id"]),
        ("ix_agent_approval_request_requested_tool", ["requested_tool"]),
        ("ix_agent_approval_request_target_id", ["target_id"]),
        ("ix_agent_approval_request_status", ["status"]),
        ("ix_agent_approval_request_approver_user_id", ["approver_user_id"]),
        ("idx_agent_approval_company_project", ["company_id", "project_id"]),
        ("idx_agent_approval_status_created", ["status", "created_at"]),
        ("idx_agent_approval_run_step", ["run_id", "step_run_id"]),
    ]:
        if not _has_index(inspector, "agent_approval_request", index_name):
            op.create_index(index_name, "agent_approval_request", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("agent_approval_request"):
        op.drop_table("agent_approval_request")
