import uuid

from sqlalchemy.orm import Session

from app.domain.work_orders import WorkOrderStatus, transition_status
from app.infrastructure.database.models import Project, SafetyWorkOrder
from app.schemas.work_orders import WorkOrderCreate


def list_work_orders(db: Session, project_id: str | None = None, status: str | None = None) -> list[dict]:
    query = db.query(SafetyWorkOrder, Project.project_name).outerjoin(
        Project,
        Project.project_id == SafetyWorkOrder.project_id,
    )
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


def create_work_order(db: Session, data: WorkOrderCreate) -> SafetyWorkOrder:
    project = None
    if data.project_id:
        project = db.query(Project).filter(Project.project_id == data.project_id).first()

    order = SafetyWorkOrder(
        work_order_id=data.work_order_id or f"WO-{uuid.uuid4().hex[:8].upper()}",
        tenant_id="CSCEC",
        org_path=project.org_path if project else f"CSCEC/CSCEC-8B/{data.project_id or 'UNKNOWN'}",
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


def update_work_order_status(db: Session, work_order_id: str, action: str) -> dict | None:
    order = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == work_order_id).first()
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
