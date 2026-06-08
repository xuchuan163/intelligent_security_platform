from sqlalchemy.orm import Session

from app.core.security import MockUser, assert_project_access
from app.domain.hazard_workflow import allowed_action
from app.infrastructure.database.models import ProjectUser, SafetyWorkOrder


def get_project_role(db: Session, current_user: MockUser, project_id: str) -> ProjectUser | None:
    return (
        db.query(ProjectUser)
        .filter(
            ProjectUser.company_id == current_user.company_id,
            ProjectUser.project_id == project_id,
            ProjectUser.user_id == current_user.user_id,
            ProjectUser.role_code == current_user.role,
            ProjectUser.status == "active",
        )
        .first()
    )


def assert_project_membership(
    db: Session,
    current_user: MockUser,
    project_id: str | None,
    role_code: str | None = None,
) -> ProjectUser:
    if not project_id:
        raise PermissionError("Project id is required")
    assert_project_access(project_id, current_user)
    if role_code and current_user.role != role_code:
        raise PermissionError("Project role is not authorized")

    role = get_project_role(db, current_user, project_id)
    if role is None:
        raise PermissionError("Project role is not authorized")
    if role_code and role.role_code != role_code:
        raise PermissionError("Project role is not authorized")
    return role


def assert_work_order_action_allowed(
    db: Session,
    current_user: MockUser,
    order: SafetyWorkOrder,
    action: str,
) -> ProjectUser:
    role = assert_project_membership(db, current_user, order.project_id, current_user.role)
    if (
        current_user.subcontractor_id
        and role.subcontractor_id
        and current_user.subcontractor_id != role.subcontractor_id
    ):
        raise PermissionError("Action is not allowed for current project role")
    subcontractor_id = role.subcontractor_id or current_user.subcontractor_id
    if not allowed_action(
        role_code=role.role_code,
        status=order.status,
        action=action,
        user_subcontractor_id=subcontractor_id,
        order_subcontractor_id=order.subcontractor_id,
    ):
        raise PermissionError("Action is not allowed for current project role")
    return role
