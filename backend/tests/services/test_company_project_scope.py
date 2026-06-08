from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser, ScopeType, apply_data_scope, assert_project_access
from app.infrastructure.database.models import Project, SafetyWorkOrder
from app.infrastructure.database.session import Base


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_mock_user_exposes_company_project_scope_with_legacy_compatibility():
    company_user = MockUser(
        user_id="u-company",
        user_name="Company User",
        tenant_id="COMPANY-A",
        org_path="COMPANY-A",
        role="company_admin",
        data_scope=DataScope.TENANT,
    )
    project_user = MockUser(
        user_id="u-project",
        user_name="Project User",
        tenant_id="COMPANY-A",
        org_path="COMPANY-A/P001",
        role="project_manager",
        data_scope=DataScope.ORG,
        authorized_project_ids=("P001",),
    )

    assert company_user.company_id == "COMPANY-A"
    assert company_user.scope_type == ScopeType.COMPANY
    assert company_user.authorized_project_ids == ()
    assert project_user.company_id == "COMPANY-A"
    assert project_user.scope_type == ScopeType.PROJECT
    assert project_user.authorized_project_ids == ("P001",)
    assert project_user.to_dict()["scope_type"] == "project"


def test_apply_data_scope_company_user_sees_same_company_projects_only():
    db = _session()
    db.add_all(
        [
            Project(project_id="P001", tenant_id="COMPANY-A", org_path="COMPANY-A/P001", project_name="P001"),
            Project(project_id="P002", tenant_id="COMPANY-A", org_path="COMPANY-A/P002", project_name="P002"),
            Project(project_id="P999", tenant_id="COMPANY-B", org_path="COMPANY-B/P999", project_name="P999"),
        ]
    )
    db.commit()
    user = MockUser(
        user_id="u-company",
        user_name="Company User",
        tenant_id="COMPANY-A",
        org_path="COMPANY-A",
        role="company_admin",
        scope_type=ScopeType.COMPANY,
    )

    rows = apply_data_scope(db.query(Project), Project, user).order_by(Project.project_id.asc()).all()

    assert [row.project_id for row in rows] == ["P001", "P002"]


def test_apply_data_scope_project_user_uses_authorized_project_ids_before_org_path():
    db = _session()
    db.add_all(
        [
            SafetyWorkOrder(
                work_order_id="WO-IN",
                tenant_id="COMPANY-A",
                org_path="COMPANY-A/legacy/mismatch",
                project_id="P001",
                work_order_type="hazard_rectification",
                title="In scope",
                status="pending_confirm",
            ),
            SafetyWorkOrder(
                work_order_id="WO-OUT",
                tenant_id="COMPANY-A",
                org_path="COMPANY-A/P001/old-prefix",
                project_id="P002",
                work_order_type="hazard_rectification",
                title="Out scope",
                status="pending_confirm",
            ),
            SafetyWorkOrder(
                work_order_id="WO-OTHER",
                tenant_id="COMPANY-B",
                org_path="COMPANY-B/P001",
                project_id="P001",
                work_order_type="hazard_rectification",
                title="Other company",
                status="pending_confirm",
            ),
        ]
    )
    db.commit()
    user = MockUser(
        user_id="u-project",
        user_name="Project User",
        tenant_id="COMPANY-A",
        org_path="COMPANY-A/legacy",
        role="project_manager",
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P001",),
    )

    rows = apply_data_scope(db.query(SafetyWorkOrder), SafetyWorkOrder, user).all()

    assert [row.work_order_id for row in rows] == ["WO-IN"]


def test_assert_project_access_rejects_project_outside_authorized_scope():
    user = MockUser(
        user_id="u-project",
        user_name="Project User",
        tenant_id="COMPANY-A",
        org_path="COMPANY-A/P001",
        role="project_manager",
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P001",),
    )

    assert_project_access("P001", user)
    try:
        assert_project_access("P002", user)
    except PermissionError as exc:
        assert "No permission to access this project" in str(exc)
    else:
        raise AssertionError("Expected PermissionError for unauthorized project")
