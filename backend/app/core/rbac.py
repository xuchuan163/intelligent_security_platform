from collections.abc import Callable, Iterable

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import MockUser, get_current_user
from app.domain.rbac import DEFAULT_ROLE_PERMISSIONS, Permission
from app.infrastructure.database.session import get_db
from app.services.auth.user_context import load_role_codes_and_permissions

LEGACY_ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "company_admin": DEFAULT_ROLE_PERMISSIONS["company_analyst"],
    "safety_manager": DEFAULT_ROLE_PERMISSIONS["project_safety_officer"],
    "safety_director": DEFAULT_ROLE_PERMISSIONS["project_safety_officer"],
    "gc_safety_officer": DEFAULT_ROLE_PERMISSIONS["project_safety_officer"],
    "sub_safety_officer": DEFAULT_ROLE_PERMISSIONS["project_safety_officer"],
    "project_safety_officer": DEFAULT_ROLE_PERMISSIONS["project_safety_officer"],
}


def resolve_effective_permissions(db: Session, user: MockUser) -> frozenset[str]:
    if user.permissions:
        return frozenset(user.permissions)

    _, db_permissions = load_role_codes_and_permissions(
        db,
        tenant_id=user.tenant_id,
        user_id=user.user_id,
    )
    if db_permissions:
        return frozenset(db_permissions)

    if user.role in DEFAULT_ROLE_PERMISSIONS:
        return frozenset(DEFAULT_ROLE_PERMISSIONS[user.role])
    if user.role in LEGACY_ROLE_PERMISSIONS:
        return frozenset(LEGACY_ROLE_PERMISSIONS[user.role])
    return frozenset()


def has_permission(db: Session, user: MockUser, permission: str) -> bool:
    if not settings.rbac_enforce:
        return True
    return permission in resolve_effective_permissions(db, user)


def assert_permissions(db: Session, user: MockUser, required: Iterable[str]) -> None:
    if not settings.rbac_enforce:
        return
    effective = resolve_effective_permissions(db, user)
    missing = [permission for permission in required if permission not in effective]
    if missing:
        raise HTTPException(
            status_code=403,
            detail=f"Missing permission: {missing[0]}",
        )


def require_permissions(*required: str | Permission) -> Callable[..., MockUser]:
    normalized = [str(permission) for permission in required]

    def _dependency(
        current_user: MockUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> MockUser:
        assert_permissions(db, current_user, normalized)
        return current_user

    return _dependency
