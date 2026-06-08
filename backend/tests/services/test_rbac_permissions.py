from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.rbac import assert_permissions, has_permission, resolve_effective_permissions
from app.core.security import DataScope, MockUser, ScopeType
from app.domain.rbac import Permission
from app.infrastructure.database.session import Base
from app.services.auth.seed_rbac import seed_rbac_foundation


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _user(role: str, permissions: tuple[str, ...] = ()) -> MockUser:
    return MockUser(
        user_id="U-TEST",
        user_name="Tester",
        tenant_id="CSCEC",
        org_path="CSCEC",
        role=role,
        data_scope=DataScope.TENANT,
        company_id="CSCEC",
        scope_type=ScopeType.COMPANY,
        permissions=permissions,
    )


def test_resolve_permissions_from_explicit_user_permissions():
    db = _session()
    try:
        user = _user("ignored", permissions=(Permission.DASHBOARD_READ,))
        effective = resolve_effective_permissions(db, user)
        assert Permission.DASHBOARD_READ in effective
        assert Permission.METRICS_READ not in effective
    finally:
        db.close()


def test_resolve_permissions_from_db_seed():
    db = _session()
    try:
        seed_rbac_foundation(db)
        db.commit()
        user = MockUser(
            user_id="mock-admin",
            user_name="Platform Admin",
            tenant_id="CSCEC",
            org_path="CSCEC",
            role="platform_admin",
            company_id="CSCEC",
            scope_type=ScopeType.COMPANY,
        )
        effective = resolve_effective_permissions(db, user)
        assert Permission.AUTH_ADMIN in effective
        assert Permission.AGENT_ASK in effective
    finally:
        db.close()


def test_role_fallback_maps_company_analyst():
    db = _session()
    try:
        user = _user("company_analyst")
        effective = resolve_effective_permissions(db, user)
        assert Permission.METRICS_READ in effective
        assert Permission.AGENT_APPROVE not in effective
    finally:
        db.close()


def test_project_officer_lacks_metrics_read():
    db = _session()
    try:
        user = _user("project_safety_officer")
        effective = resolve_effective_permissions(db, user)
        assert Permission.WORK_ORDERS_WRITE in effective
        assert Permission.METRICS_READ not in effective
    finally:
        db.close()


def test_assert_permissions_raises_for_missing_permission(monkeypatch):
    monkeypatch.setattr(settings, "rbac_enforce", True)
    db = _session()
    try:
        user = _user("company_analyst")
        assert has_permission(db, user, Permission.METRICS_READ)
        assert not has_permission(db, user, Permission.AGENT_APPROVE)
        try:
            assert_permissions(db, user, [Permission.AGENT_APPROVE])
            assert False, "expected HTTPException"
        except Exception as exc:
            assert getattr(exc, "status_code", None) == 403
    finally:
        db.close()


def test_rbac_enforce_disabled_allows_all(monkeypatch):
    monkeypatch.setattr(settings, "rbac_enforce", False)
    db = _session()
    try:
        user = _user("unknown_role")
        assert has_permission(db, user, Permission.AUTH_ADMIN)
        assert_permissions(db, user, [Permission.AUTH_ADMIN])
    finally:
        db.close()
