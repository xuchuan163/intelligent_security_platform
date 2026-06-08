from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.infrastructure.database.models import AuthRole, UserAccount, UserRole
from app.infrastructure.database.session import Base
from app.services.auth.seed_rbac import seed_rbac_foundation


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_seed_rbac_foundation_is_idempotent():
    db = _session()
    try:
        seed_rbac_foundation(db, tenant_id="CSCEC", company_id="CSCEC")
        db.commit()
        role_count = db.query(AuthRole).count()
        user_count = db.query(UserAccount).count()
        assignment_count = db.query(UserRole).count()

        seed_rbac_foundation(db, tenant_id="CSCEC", company_id="CSCEC")
        db.commit()

        assert db.query(AuthRole).count() == role_count == 3
        assert db.query(UserAccount).count() == user_count == 4
        assert db.query(UserRole).count() == assignment_count == 4

        admin = db.query(UserAccount).filter(UserAccount.user_id == "mock-admin").one()
        assert admin.scope_type == "company"
        platform_role = db.query(AuthRole).filter(AuthRole.role_code == "platform_admin").one()
        assert "auth.admin" in platform_role.permissions
        assert "agent.ask" in platform_role.permissions
    finally:
        db.close()


def test_project_officer_seed_carries_authorized_project_ids():
    db = _session()
    try:
        seed_rbac_foundation(db)
        db.commit()
        pm = db.query(UserAccount).filter(UserAccount.user_id == "U-PM-P001").one()
        assert pm.authorized_project_ids == ["P001"]
        assignment = (
            db.query(UserRole)
            .filter(UserRole.user_id == "U-PM-P001", UserRole.project_id == "P001")
            .one()
        )
        assert assignment.role_code == "project_safety_officer"
    finally:
        db.close()
