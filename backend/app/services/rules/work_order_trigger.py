import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.infrastructure.database.models import SafetyWorkOrder

OPEN_STATUSES = {
    "pending_confirm",
    "dispatched",
    "processing",
    "waiting_review",
    "rejected",
    "overdue_escalated",
}


@dataclass
class WorkOrderTriggerStats:
    created_work_orders: int = 0
    skipped_duplicate_work_orders: int = 0

    def add(self, other: "WorkOrderTriggerStats") -> None:
        self.created_work_orders += other.created_work_orders
        self.skipped_duplicate_work_orders += other.skipped_duplicate_work_orders

    def to_dict(self) -> dict:
        return {
            "created_work_orders": self.created_work_orders,
            "skipped_duplicate_work_orders": self.skipped_duplicate_work_orders,
        }


def create_work_orders_for_rule_triggers(
    db: Session,
    triggers: list[dict],
    source,
    object_type: str,
    object_id: str,
    project_id: str | None,
) -> WorkOrderTriggerStats:
    stats = WorkOrderTriggerStats()
    for trigger in triggers:
        if not trigger.get("auto_create_work_order"):
            continue
        if _has_open_duplicate(db, trigger["rule_id"], object_type, object_id, project_id):
            stats.skipped_duplicate_work_orders += 1
            continue

        db.add(
            SafetyWorkOrder(
                work_order_id=f"WO-{uuid.uuid4().hex[:8].upper()}",
                tenant_id=source.tenant_id,
                org_path=source.org_path,
                work_order_type=trigger.get("suggested_work_order_type") or "hazard_rectification",
                source_type=object_type,
                source_id=object_id,
                project_id=project_id,
                worker_id=object_id if object_type == "worker" else None,
                subcontractor_id=getattr(source, "subcontractor_id", None),
                title=_work_order_title(trigger, object_id),
                description=_work_order_description(trigger),
                priority=trigger.get("work_order_priority") or "normal",
                rule_id=trigger["rule_id"],
                status="pending_confirm",
            )
        )
        stats.created_work_orders += 1
    return stats


def _has_open_duplicate(
    db: Session,
    rule_id: str,
    source_type: str,
    source_id: str,
    project_id: str | None,
) -> bool:
    query = db.query(SafetyWorkOrder).filter(
        SafetyWorkOrder.rule_id == rule_id,
        SafetyWorkOrder.source_type == source_type,
        SafetyWorkOrder.source_id == source_id,
        SafetyWorkOrder.status.in_(OPEN_STATUSES),
    )
    if project_id is None:
        query = query.filter(SafetyWorkOrder.project_id.is_(None))
    else:
        query = query.filter(SafetyWorkOrder.project_id == project_id)
    return query.first() is not None


def _work_order_title(trigger: dict, object_id: str) -> str:
    template = trigger.get("work_order_title_template") or f"{trigger['rule_name']}整改"
    return template.format(object_id=object_id, rule_name=trigger["rule_name"])


def _work_order_description(trigger: dict) -> str:
    return f"规则{trigger['rule_id']}触发：{trigger['rule_name']}。请依据 evidence 核查并闭环整改。"
