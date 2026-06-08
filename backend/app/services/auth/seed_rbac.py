"""Idempotent RBAC seed aligned with mock headers and hazard workflow demo users."""

from sqlalchemy.orm import Session

from app.core.config import settings
from app.domain.rbac import DEFAULT_ROLE_PERMISSIONS
from app.infrastructure.database.models import AuthRole, UserAccount, UserRole
from app.services.auth.passwords import hash_password


def _upsert_role(db: Session, *, tenant_id: str, role_code: str, role_name: str, scope_type: str) -> AuthRole:
    role = (
        db.query(AuthRole)
        .filter(AuthRole.tenant_id == tenant_id, AuthRole.role_code == role_code)
        .first()
    )
    permissions = list(DEFAULT_ROLE_PERMISSIONS[role_code])
    if role is None:
        role = AuthRole(
            tenant_id=tenant_id,
            role_code=role_code,
            role_name=role_name,
            scope_type=scope_type,
            permissions=permissions,
        )
        db.add(role)
        db.flush()
    else:
        role.role_name = role_name
        role.scope_type = scope_type
        role.permissions = permissions
        role.status = "active"
    return role


def _upsert_user(
    db: Session,
    *,
    tenant_id: str,
    company_id: str,
    org_path: str,
    user_id: str,
    user_name: str,
    scope_type: str,
    authorized_project_ids: list[str] | None = None,
    subcontractor_id: str | None = None,
    email: str | None = None,
) -> UserAccount:
    user = (
        db.query(UserAccount)
        .filter(UserAccount.tenant_id == tenant_id, UserAccount.user_id == user_id)
        .first()
    )
    if user is None:
        user = UserAccount(
            tenant_id=tenant_id,
            company_id=company_id,
            org_path=org_path,
            user_id=user_id,
            user_name=user_name,
            scope_type=scope_type,
        )
        db.add(user)
    user.company_id = company_id
    user.org_path = org_path
    user.user_name = user_name
    user.scope_type = scope_type
    user.authorized_project_ids = authorized_project_ids
    user.subcontractor_id = subcontractor_id
    user.email = email
    user.status = "active"
    if not user.password_hash:
        user.password_hash = hash_password(settings.demo_default_password)
    return user


def _upsert_user_role(
    db: Session,
    *,
    tenant_id: str,
    company_id: str,
    user_id: str,
    role: AuthRole,
    project_id: str = "",
) -> UserRole:
    assignment = (
        db.query(UserRole)
        .filter(
            UserRole.tenant_id == tenant_id,
            UserRole.user_id == user_id,
            UserRole.role_id == role.id,
            UserRole.project_id == project_id,
        )
        .first()
    )
    if assignment is None:
        assignment = UserRole(
            tenant_id=tenant_id,
            company_id=company_id,
            user_id=user_id,
            role_id=role.id,
            role_code=role.role_code,
            project_id=project_id,
        )
        db.add(assignment)
    assignment.company_id = company_id
    assignment.role_code = role.role_code
    assignment.status = "active"
    return assignment


def seed_rbac_foundation(db: Session, tenant_id: str = "CSCEC", company_id: str = "CSCEC") -> None:
    """Seed default roles and demo accounts for JWT migration (3-A.2)."""

    platform_admin = _upsert_role(
        db,
        tenant_id=tenant_id,
        role_code="platform_admin",
        role_name="平台管理员",
        scope_type="company",
    )
    company_analyst = _upsert_role(
        db,
        tenant_id=tenant_id,
        role_code="company_analyst",
        role_name="公司级分析员",
        scope_type="company",
    )
    project_officer = _upsert_role(
        db,
        tenant_id=tenant_id,
        role_code="project_safety_officer",
        role_name="项目安全负责人",
        scope_type="project",
    )

    admin_user = _upsert_user(
        db,
        tenant_id=tenant_id,
        company_id=company_id,
        org_path=company_id,
        user_id="mock-admin",
        user_name="Platform Admin",
        scope_type="company",
        email="admin@demo.local",
    )
    _upsert_user_role(db, tenant_id=tenant_id, company_id=company_id, user_id=admin_user.user_id, role=platform_admin)

    director = _upsert_user(
        db,
        tenant_id=tenant_id,
        company_id=company_id,
        org_path=f"{company_id}/CSCEC-8B/EAST-REGION/P002",
        user_id="U-DIR-01",
        user_name="王总监",
        scope_type="project",
        authorized_project_ids=["P002"],
    )
    _upsert_user_role(
        db,
        tenant_id=tenant_id,
        company_id=company_id,
        user_id=director.user_id,
        role=project_officer,
        project_id="P002",
    )

    pm_user = _upsert_user(
        db,
        tenant_id=tenant_id,
        company_id=company_id,
        org_path=f"{company_id}/CSCEC-8B/EAST-REGION/P001",
        user_id="U-PM-P001",
        user_name="张项目",
        scope_type="project",
        authorized_project_ids=["P001"],
    )
    _upsert_user_role(
        db,
        tenant_id=tenant_id,
        company_id=company_id,
        user_id=pm_user.user_id,
        role=project_officer,
        project_id="P001",
    )

    analyst = _upsert_user(
        db,
        tenant_id=tenant_id,
        company_id=company_id,
        org_path=company_id,
        user_id="U-CO-ANALYST",
        user_name="公司分析员",
        scope_type="company",
    )
    _upsert_user_role(db, tenant_id=tenant_id, company_id=company_id, user_id=analyst.user_id, role=company_analyst)
