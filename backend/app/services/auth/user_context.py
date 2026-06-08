from sqlalchemy.orm import Session

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import AuthRole, UserAccount, UserRole


def _normalize_project_ids(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return ()
    return tuple(sorted({item for item in values if item}))


def load_role_codes_and_permissions(
    db: Session,
    *,
    tenant_id: str,
    user_id: str,
) -> tuple[list[str], list[str]]:
    rows = (
        db.query(UserRole.role_code, AuthRole.permissions)
        .join(AuthRole, AuthRole.id == UserRole.role_id)
        .filter(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id == user_id,
            UserRole.status == "active",
            AuthRole.status == "active",
        )
        .all()
    )
    role_codes: list[str] = []
    permission_set: set[str] = set()
    for role_code, permissions in rows:
        if role_code not in role_codes:
            role_codes.append(role_code)
        if isinstance(permissions, list):
            permission_set.update(str(item) for item in permissions)
    return role_codes, sorted(permission_set)


def build_mock_user_from_account(db: Session, account: UserAccount, *, auth_source: str = "jwt") -> MockUser:
    role_codes, permissions = load_role_codes_and_permissions(
        db,
        tenant_id=account.tenant_id,
        user_id=account.user_id,
    )
    scope_type = ScopeType(account.scope_type) if account.scope_type in ScopeType._value2member_map_ else ScopeType.COMPANY
    authorized_project_ids = _normalize_project_ids(account.authorized_project_ids)
    data_scope = DataScope.ORG if scope_type == ScopeType.PROJECT else DataScope.TENANT
    primary_role = role_codes[0] if role_codes else "anonymous"

    user = MockUser(
        user_id=account.user_id,
        user_name=account.user_name,
        tenant_id=account.tenant_id,
        org_path=account.org_path,
        role=primary_role,
        data_scope=data_scope,
        company_id=account.company_id,
        scope_type=scope_type,
        authorized_project_ids=authorized_project_ids,
        subcontractor_id=account.subcontractor_id,
        permissions=tuple(permissions),
        roles=tuple(role_codes),
        auth_source=auth_source,
    )
    return user


def user_profile_dict(user: MockUser) -> dict:
    data = user.to_dict()
    data["roles"] = list(user.roles)
    data["permissions"] = list(user.permissions)
    data["auth_source"] = user.auth_source
    return data
