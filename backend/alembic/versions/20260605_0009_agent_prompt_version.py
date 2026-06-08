"""add agent prompt version table

Revision ID: 20260605_0009
Revises: 20260605_0008
Create Date: 2026-06-05
"""

from alembic import op
import sqlalchemy as sa


revision = "20260605_0009"
down_revision = "20260605_0008"
branch_labels = None
depends_on = None


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("agent_prompt_version"):
        op.create_table(
            "agent_prompt_version",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("agent_code", sa.String(length=64), nullable=False),
            sa.Column("prompt_version", sa.String(length=32), nullable=False),
            sa.Column("prompt_path", sa.String(length=255), nullable=False),
            sa.Column("prompt_hash", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_code", "prompt_version", name="uk_agent_prompt_version"),
        )
    inspector = sa.inspect(bind)
    if inspector.has_table("agent_prompt_version"):
        for index_name, columns in [
            ("ix_agent_prompt_version_agent_code", ["agent_code"]),
            ("idx_agent_prompt_active", ["agent_code", "is_active"]),
        ]:
            if not _has_index(inspector, "agent_prompt_version", index_name):
                op.create_index(index_name, "agent_prompt_version", columns)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("agent_prompt_version"):
        op.drop_table("agent_prompt_version")
