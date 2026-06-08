import datetime
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import MockUser, apply_data_scope
from app.domain.work_orders import WorkOrderStatus, transition_status
from app.infrastructure.database.models import Project, SafetyWorkOrder, WorkOrderFlowLog
from app.schemas.work_orders import WorkOrderCreate


def list_work_orders(
    db: Session,
    project_id: str | None = None,
    status: str | None = None,
    current_user: MockUser | None = None,
) -> list[dict]:
    query = db.query(SafetyWorkOrder, Project.project_name).outerjoin(
        Project,
        Project.project_id == SafetyWorkOrder.project_id,
    )
    if current_user:
        query = apply_data_scope(query, SafetyWorkOrder, current_user)
    if project_id:
        query = query.filter(SafetyWorkOrder.project_id == project_id)
    if status:
        query = query.filter(SafetyWorkOrder.status == status)

    rows = query.order_by(SafetyWorkOrder.created_at.desc()).limit(100).all()
    return [
        {
            "work_order_id": row.SafetyWorkOrder.work_order_id,
            "work_order_type": row.SafetyWorkOrder.work_order_type,
            "title": row.SafetyWorkOrder.title,
            "description": row.SafetyWorkOrder.description,
            "project_id": row.SafetyWorkOrder.project_id,
            "project_name": row.project_name,
            "subcontractor_id": row.SafetyWorkOrder.subcontractor_id,
            "worker_id": row.SafetyWorkOrder.worker_id,
            "equipment_id": row.SafetyWorkOrder.equipment_id,
            "status": row.SafetyWorkOrder.status,
            "priority": row.SafetyWorkOrder.priority,
            "due_time": row.SafetyWorkOrder.due_time.isoformat() if row.SafetyWorkOrder.due_time else None,
            "escalation_level": row.SafetyWorkOrder.escalation_level,
            "rule_id": row.SafetyWorkOrder.rule_id,
            "created_at": row.SafetyWorkOrder.created_at.isoformat(),
        }
        for row in rows
    ]


def get_work_order_detail(
    db: Session,
    work_order_id: str,
    current_user: MockUser | None = None,
) -> dict | None:
    query = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == work_order_id)
    if current_user:
        query = apply_data_scope(query, SafetyWorkOrder, current_user)
    order = query.first()
    if order is None:
        return None

    flow_logs = (
        db.query(WorkOrderFlowLog)
        .filter(WorkOrderFlowLog.work_order_id == work_order_id)
        .order_by(WorkOrderFlowLog.created_at.asc(), WorkOrderFlowLog.id.asc())
        .all()
    )
    return {
        "work_order_id": order.work_order_id,
        "work_order_type": order.work_order_type,
        "source_type": order.source_type,
        "source_id": order.source_id,
        "title": order.title,
        "description": order.description,
        "project_id": order.project_id,
        "subcontractor_id": order.subcontractor_id,
        "worker_id": order.worker_id,
        "equipment_id": order.equipment_id,
        "status": order.status,
        "priority": order.priority,
        "responsible_user_id": order.responsible_user_id,
        "review_user_id": order.review_user_id,
        "due_time": order.due_time.isoformat() if order.due_time else None,
        "review_time": order.review_time.isoformat() if order.review_time else None,
        "close_time": order.close_time.isoformat() if order.close_time else None,
        "reject_reason": order.reject_reason,
        "attachments": order.attachments,
        "created_at": order.created_at.isoformat(),
        "flow_logs": [
            {
                "from_status": log.from_status,
                "to_status": log.to_status,
                "action": log.action,
                "operator_user_id": log.operator_user_id,
                "operator_role": log.operator_role,
                "comment": log.comment,
                "reject_reason": log.reject_reason,
                "attachments": log.attachments,
                "created_at": log.created_at.isoformat(),
            }
            for log in flow_logs
        ],
    }


def create_work_order(db: Session, data: WorkOrderCreate, current_user: MockUser | None = None) -> SafetyWorkOrder:
    project = None
    if data.project_id:
        project = db.query(Project).filter(Project.project_id == data.project_id).first()
        if project and current_user:
            scoped_project = apply_data_scope(db.query(Project), Project, current_user).filter(
                Project.project_id == data.project_id,
            )
            project = scoped_project.first()
            if project is None:
                raise PermissionError("Project is outside current user data scope")

    order = SafetyWorkOrder(
        work_order_id=data.work_order_id or f"WO-{uuid.uuid4().hex[:8].upper()}",
        tenant_id=current_user.tenant_id if current_user else "CSCEC",
        org_path=project.org_path if project else _default_org_path(data.project_id, current_user),
        work_order_type=data.work_order_type,
        source_type=data.source_type,
        source_id=data.source_id,
        project_id=data.project_id,
        subcontractor_id=data.subcontractor_id,
        worker_id=data.worker_id,
        equipment_id=data.equipment_id,
        title=data.title,
        description=data.description,
        priority=data.priority,
        due_time=data.due_time,
        rule_id=data.rule_id,
        responsible_user_id=data.responsible_user_id,
        status="pending_confirm",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def update_work_order_status(
    db: Session,
    work_order_id: str,
    action: str,
    current_user: MockUser | None = None,
) -> dict | None:
    query = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == work_order_id)
    if current_user:
        query = apply_data_scope(query, SafetyWorkOrder, current_user)
    order = query.first()
    if not order:
        return None

    try:
        current = WorkOrderStatus(order.status)
        new_status = transition_status(current, action)
        order.status = new_status.value
        db.commit()
        return {"work_order_id": work_order_id, "new_status": new_status.value}
    except ValueError as exc:
        return {"work_order_id": work_order_id, "error": str(exc)}


def escalate_overdue_work_orders(
    db: Session,
    current_user: MockUser | None = None,
    now: datetime.datetime | None = None,
    timeout_hours: int | None = None,
) -> dict:
    """Escalate processing work orders that have passed due time or timeout window."""
    now = now or datetime.datetime.utcnow()
    timeout_hours = timeout_hours or settings.processing_timeout_hours
    timeout_before = now - datetime.timedelta(hours=timeout_hours)

    query = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.status == WorkOrderStatus.PROCESSING.value)
    if current_user:
        query = apply_data_scope(query, SafetyWorkOrder, current_user)
    orders = query.order_by(SafetyWorkOrder.updated_at.asc()).all()

    escalated_ids: list[str] = []
    for order in orders:
        if not _is_work_order_overdue(order, now, timeout_before):
            continue

        new_status = transition_status(WorkOrderStatus(order.status), "timeout")
        order.status = new_status.value
        order.escalation_level = (order.escalation_level or 0) + 1
        order.escalation_history = _append_escalation_event(order.escalation_history, order, now)
        escalated_ids.append(order.work_order_id)

    db.commit()
    return {
        "scanned_work_orders": len(orders),
        "escalated_work_orders": len(escalated_ids),
        "skipped_work_orders": len(orders) - len(escalated_ids),
        "work_order_ids": escalated_ids,
    }


def _default_org_path(project_id: str | None, current_user: MockUser | None) -> str:
    if current_user:
        return f"{current_user.org_path}/{project_id or 'UNKNOWN'}"
    return f"CSCEC/CSCEC-8B/{project_id or 'UNKNOWN'}"


def _is_work_order_overdue(
    order: SafetyWorkOrder,
    now: datetime.datetime,
    timeout_before: datetime.datetime,
) -> bool:
    if order.due_time and order.due_time < now:
        return True
    return bool(order.due_time is None and order.updated_at and order.updated_at < timeout_before)


def _append_escalation_event(
    history: dict | None,
    order: SafetyWorkOrder,
    now: datetime.datetime,
) -> dict:
    payload = dict(history or {})
    events = list(payload.get("events") or [])
    events.append(
        {
            "action": "timeout",
            "from_status": WorkOrderStatus.PROCESSING.value,
            "to_status": WorkOrderStatus.OVERDUE_ESCALATED.value,
            "work_order_id": order.work_order_id,
            "escalated_at": now.isoformat(),
            "reason": "processing work order overdue",
        }
    )
    payload["events"] = events
    return payload
