"""user rbac foundation tables

Revision ID: 20260609_0014
Revises: 20260608_0013
Create Date: 2026-06-09
"""

from alembic import op
import sqlalchemy as sa


revision = "20260609_0014"
down_revision = "20260608_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("user_account"):
        op.create_table(
            "user_account",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("org_path", sa.String(length=512), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("user_name", sa.String(length=128), nullable=False),
            sa.Column("email", sa.String(length=255), nullable=True),
            sa.Column("password_hash", sa.String(length=255), nullable=True),
            sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="company"),
            sa.Column("authorized_project_ids", sa.JSON(), nullable=True),
            sa.Column("subcontractor_id", sa.String(length=64), nullable=True),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("last_login_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "user_id", name="uk_user_account_tenant_user"),
        )
        op.create_index("ix_user_account_tenant_id", "user_account", ["tenant_id"])
        op.create_index("ix_user_account_company_id", "user_account", ["company_id"])
        op.create_index("ix_user_account_user_id", "user_account", ["user_id"])
        op.create_index("ix_user_account_subcontractor_id", "user_account", ["subcontractor_id"])
        op.create_index("idx_user_account_company_user", "user_account", ["company_id", "user_id"])

    if not inspector.has_table("auth_role"):
        op.create_table(
            "auth_role",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("role_code", sa.String(length=64), nullable=False),
            sa.Column("role_name", sa.String(length=128), nullable=False),
            sa.Column("scope_type", sa.String(length=32), nullable=False, server_default="company"),
            sa.Column("permissions", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "role_code", name="uk_auth_role_tenant_code"),
        )
        op.create_index("ix_auth_role_tenant_id", "auth_role", ["tenant_id"])
        op.create_index("ix_auth_role_role_code", "auth_role", ["role_code"])

    if not inspector.has_table("user_role"):
        op.create_table(
            "user_role",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.String(length=64), nullable=False),
            sa.Column("company_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.String(length=64), nullable=False),
            sa.Column("role_id", sa.Integer(), nullable=False),
            sa.Column("role_code", sa.String(length=64), nullable=False),
            sa.Column("project_id", sa.String(length=64), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "user_id", "role_id", "project_id", name="uk_user_role_scope"),
        )
        op.create_index("ix_user_role_tenant_id", "user_role", ["tenant_id"])
        op.create_index("ix_user_role_company_id", "user_role", ["company_id"])
        op.create_index("ix_user_role_user_id", "user_role", ["user_id"])
        op.create_index("ix_user_role_role_id", "user_role", ["role_id"])
        op.create_index("ix_user_role_role_code", "user_role", ["role_code"])
        op.create_index("ix_user_role_project_id", "user_role", ["project_id"])
        op.create_index("idx_user_role_company_user", "user_role", ["company_id", "user_id"])
        op.create_index("idx_user_role_project", "user_role", ["project_id", "role_code"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("user_role"):
        op.drop_table("user_role")
    if inspector.has_table("auth_role"):
        op.drop_table("auth_role")
    if inspector.has_table("user_account"):
        op.drop_table("user_account")
