"""add accident case library table

Revision ID: 20260604_0002
Revises: 20260602_0001
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0002"
down_revision = "20260602_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("accident_case_library"):
        return

    op.create_table(
        "accident_case_library",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("accident_case_id", sa.String(length=64), nullable=False),
        sa.Column("tenant_id", sa.String(length=64), nullable=False),
        sa.Column("accident_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("project_type", sa.String(length=64), nullable=True),
        sa.Column("operation_scene", sa.String(length=64), nullable=True),
        sa.Column("direct_cause", sa.Text(), nullable=True),
        sa.Column("indirect_cause", sa.Text(), nullable=True),
        sa.Column("involved_subjects", sa.JSON(), nullable=True),
        sa.Column("warning_indicators", sa.JSON(), nullable=True),
        sa.Column("rectification_measures", sa.Text(), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("embedding_version", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accident_case_id", name="uk_accident_case_id"),
    )
    op.create_index("ix_accident_case_library_accident_case_id", "accident_case_library", ["accident_case_id"])
    op.create_index("ix_accident_case_library_tenant_id", "accident_case_library", ["tenant_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("accident_case_library"):
        return

    op.drop_index("ix_accident_case_library_tenant_id", table_name="accident_case_library")
    op.drop_index("ix_accident_case_library_accident_case_id", table_name="accident_case_library")
    op.drop_table("accident_case_library")
