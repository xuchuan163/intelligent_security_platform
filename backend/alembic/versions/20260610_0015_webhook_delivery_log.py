"""add webhook delivery log table

Revision ID: 20260610_0015
Revises: 20260609_0014
Create Date: 2026-06-10
"""

from alembic import op
import sqlalchemy as sa


revision = "20260610_0015"
down_revision = "20260609_0014"
branch_labels = None
depends_on = None


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("webhook_delivery_log"):
        op.create_table(
            "webhook_delivery_log",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("delivery_id", sa.String(length=64), nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("org_path", sa.String(length=512), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=True),
            sa.Column("event_type", sa.String(length=64), nullable=False),
            sa.Column("event_id", sa.String(length=64), nullable=True),
            sa.Column("channel", sa.String(length=32), nullable=False),
            sa.Column("target_url_masked", sa.String(length=512), nullable=True),
            sa.Column("request_payload", sa.JSON(), nullable=True),
            sa.Column("response_status_code", sa.Integer(), nullable=True),
            sa.Column("response_body", sa.Text(), nullable=True),
            sa.Column("delivery_status", sa.String(length=32), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=False),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("need_human_review", sa.Boolean(), nullable=False),
            sa.Column("triggered_by", sa.String(length=64), nullable=True),
            sa.Column("elapsed_ms", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("delivered_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("delivery_id", name="uk_webhook_delivery_id"),
        )

    inspector = sa.inspect(bind)
    if not inspector.has_table("webhook_delivery_log"):
        return

    for index_name, columns in [
        ("ix_webhook_delivery_log_delivery_id", ["delivery_id"]),
        ("ix_webhook_delivery_log_tenant_id", ["tenant_id"]),
        ("ix_webhook_delivery_log_company_id", ["company_id"]),
        ("ix_webhook_delivery_log_org_path", ["org_path"]),
        ("ix_webhook_delivery_log_project_id", ["project_id"]),
        ("ix_webhook_delivery_log_event_type", ["event_type"]),
        ("ix_webhook_delivery_log_event_id", ["event_id"]),
        ("ix_webhook_delivery_log_delivery_status", ["delivery_status"]),
        ("idx_webhook_delivery_company_project", ["company_id", "project_id"]),
        ("idx_webhook_delivery_status_time", ["delivery_status", "created_at"]),
        ("idx_webhook_delivery_event_time", ["event_type", "created_at"]),
    ]:
        if not _has_index(inspector, "webhook_delivery_log", index_name):
            op.create_index(index_name, "webhook_delivery_log", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("webhook_delivery_log"):
        op.drop_table("webhook_delivery_log")
