from app.domain.rbac import DEFAULT_ROLE_PERMISSIONS, Permission
from app.infrastructure.database.models import AuthRole, UserAccount, UserRole


def test_user_account_declares_login_and_scope_columns():
    columns = set(UserAccount.__table__.columns.keys())
    assert {
        "tenant_id",
        "company_id",
        "org_path",
        "user_id",
        "user_name",
        "email",
        "password_hash",
        "scope_type",
        "authorized_project_ids",
        "subcontractor_id",
        "status",
    } <= columns


def test_auth_role_declares_permission_bundle_columns():
    columns = set(AuthRole.__table__.columns.keys())
    assert {
        "tenant_id",
        "role_code",
        "role_name",
        "scope_type",
        "permissions",
        "status",
    } <= columns


def test_user_role_links_user_to_role_with_optional_project_scope():
    columns = set(UserRole.__table__.columns.keys())
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in UserRole.__table__.constraints
        if getattr(constraint, "columns", None)
    }

    assert {
        "tenant_id",
        "company_id",
        "user_id",
        "role_id",
        "role_code",
        "project_id",
        "status",
    } <= columns
    assert ("tenant_id", "user_id", "role_id", "project_id") in constraints


def test_user_account_has_unique_tenant_user_constraint():
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in UserAccount.__table__.constraints
        if getattr(constraint, "columns", None)
    }
    assert ("tenant_id", "user_id") in constraints


def test_auth_role_has_unique_tenant_role_code_constraint():
    constraints = {
        tuple(column.name for column in constraint.columns)
        for constraint in AuthRole.__table__.constraints
        if getattr(constraint, "columns", None)
    }
    assert ("tenant_id", "role_code") in constraints


def test_default_role_permission_bundles_cover_phase3_gate_permissions():
    merged = {permission for permissions in DEFAULT_ROLE_PERMISSIONS.values() for permission in permissions}
    assert Permission.DASHBOARD_READ in merged
    assert Permission.AGENT_ASK in merged
    assert Permission.AUTH_ADMIN in DEFAULT_ROLE_PERMISSIONS["platform_admin"]
