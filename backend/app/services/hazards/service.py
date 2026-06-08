import datetime as dt
import uuid

from sqlalchemy.orm import Session

from app.core.permissions import assert_project_membership
from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import Hazard, Project, SafetyWorkOrder, WorkOrderFlowLog
from app.schemas.hazards import HazardCreatePayload

ROLE_GC_SAFETY_OFFICER = "gc_safety_officer"


def create_hazard_with_work_order(
    db: Session,
    project_id: str,
    payload: HazardCreatePayload,
    discovery_attachments: list[dict],
    current_user: MockUser,
) -> dict:
    assert_project_membership(db, current_user, project_id, ROLE_GC_SAFETY_OFFICER)
    if not discovery_attachments:
        raise ValueError("At least one discovery image is required")

    project = apply_data_scope(db.query(Project), Project, current_user).filter(Project.project_id == project_id).first()
    if project is None:
        raise PermissionError("Project is outside current user data scope")

    attachments = {"items": list(discovery_attachments)}
    hazard_id = f"H-{uuid.uuid4().hex[:8].upper()}"
    work_order_id = f"WO-{uuid.uuid4().hex[:8].upper()}"

    hazard = Hazard(
        hazard_id=hazard_id,
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        org_path=project.org_path,
        project_id=project_id,
        subcontractor_id=payload.subcontractor_id,
        hazard_type=payload.hazard_type,
        hazard_level=payload.hazard_level,
        description=payload.description,
        status="open",
        due_date=payload.due_date,
        is_major=payload.hazard_level == "major",
        discovered_by_user_id=current_user.user_id,
        location=payload.location,
        attachments=attachments,
        work_order_id=work_order_id,
    )
    order = SafetyWorkOrder(
        work_order_id=work_order_id,
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        org_path=project.org_path,
        work_order_type="hazard_rectification",
        source_type="hazard",
        source_id=hazard_id,
        project_id=project_id,
        subcontractor_id=payload.subcontractor_id,
        title=f"{payload.hazard_type}隐患整改",
        description=payload.description,
        priority="high" if payload.hazard_level == "major" else "normal",
        status="pending_confirm",
        due_time=dt.datetime.combine(payload.due_date, dt.time(hour=18)),
        attachments=attachments,
    )
    flow_log = WorkOrderFlowLog(
        work_order_id=work_order_id,
        from_status=None,
        to_status="pending_confirm",
        action="create",
        operator_user_id=current_user.user_id,
        operator_role=current_user.role,
        comment="隐患上传自动创建整改工单",
        attachments=attachments,
    )

    db.add_all([hazard, order, flow_log])
    db.commit()
    return {
        "hazard_id": hazard_id,
        "work_order_id": work_order_id,
        "status": "open",
        "work_order_status": "pending_confirm",
    }
