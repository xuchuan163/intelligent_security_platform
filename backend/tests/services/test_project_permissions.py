from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.permissions import (
    assert_project_membership,
    assert_work_order_action_allowed,
    get_project_role,
)
from app.core.security import DataScope, MockUser, ScopeType, get_current_user
from app.infrastructure.database.models import ProjectUser, SafetyWorkOrder
from app.infrastructure.database.session import Base


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _project_user(user_id: str, role_code: str, subcontractor_id: str | None = None) -> MockUser:
    return MockUser(
        user_id=user_id,
        user_name=user_id,
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        role=role_code,
        data_scope=DataScope.ORG,
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P002",),
        subcontractor_id=subcontractor_id,
    )


def _seed_project_users(db):
    db.add_all(
        [
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-GC-01",
                user_name="李安全",
                role_code="gc_safety_officer",
            ),
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-DIR-01",
                user_name="王总监",
                role_code="safety_director",
            ),
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-SUB-S003",
                user_name="陈分包",
                role_code="sub_safety_officer",
                subcontractor_id="S003",
            ),
        ]
    )
    db.commit()


def test_get_current_user_reads_subcontractor_header():
    user = get_current_user(
        credentials=None,
        x_mock_user_id="U-SUB-S003",
        x_role="sub_safety_officer",
        x_scope_type="project",
        x_authorized_project_ids="P002",
        x_subcontractor_id="S003",
    )

    assert user.subcontractor_id == "S003"


def test_project_membership_uses_project_user_table_not_header_only():
    db = _session()
    _seed_project_users(db)

    role = get_project_role(db, _project_user("U-DIR-01", "safety_director"), "P002")

    assert role is not None
    assert role.role_code == "safety_director"
    assert_project_membership(db, _project_user("U-DIR-01", "safety_director"), "P002", "safety_director")

    spoofed = _project_user("U-SUB-S003", "safety_director", subcontractor_id="S003")
    try:
        assert_project_membership(db, spoofed, "P002", "safety_director")
    except PermissionError as exc:
        assert "Project role is not authorized" in str(exc)
    else:
        raise AssertionError("Expected PermissionError for spoofed role")


def test_work_order_action_permission_checks_role_status_project_and_subcontractor():
    db = _session()
    _seed_project_users(db)
    order = SafetyWorkOrder(
        work_order_id="WO-001",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        work_order_type="hazard_rectification",
        project_id="P002",
        subcontractor_id="S003",
        status="pending_confirm",
    )

    assert_work_order_action_allowed(db, _project_user("U-DIR-01", "safety_director"), order, "confirm")

    try:
        assert_work_order_action_allowed(db, _project_user("U-GC-01", "gc_safety_officer"), order, "confirm")
    except PermissionError as exc:
        assert "Action is not allowed" in str(exc)
    else:
        raise AssertionError("Expected PermissionError for wrong role")

    order.status = "processing"
    assert_work_order_action_allowed(
        db,
        _project_user("U-SUB-S003", "sub_safety_officer", subcontractor_id="S003"),
        order,
        "submit_result",
    )

    try:
        assert_work_order_action_allowed(
            db,
            _project_user("U-SUB-S003", "sub_safety_officer", subcontractor_id="S999"),
            order,
            "submit_result",
        )
    except PermissionError as exc:
        assert "Action is not allowed" in str(exc)
    else:
        raise AssertionError("Expected PermissionError for wrong subcontractor")
