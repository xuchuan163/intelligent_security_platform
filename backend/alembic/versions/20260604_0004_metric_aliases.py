"""add metric aliases

Revision ID: 20260604_0004
Revises: 20260604_0003
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa


revision = "20260604_0004"
down_revision = "20260604_0003"
branch_labels = None
depends_on = None


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not _has_column(inspector, "metric_catalog", "aliases"):
        op.add_column("metric_catalog", sa.Column("aliases", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if _has_column(inspector, "metric_catalog", "aliases"):
        op.drop_column("metric_catalog", "aliases")
