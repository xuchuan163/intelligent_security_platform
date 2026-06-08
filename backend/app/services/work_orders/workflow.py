import datetime as dt

from sqlalchemy.orm import Session

from app.core.permissions import assert_work_order_action_allowed
from app.core.security import MockUser, apply_data_scope
from app.domain.work_orders import WorkOrderStatus, transition_status
from app.infrastructure.database.models import Hazard, SafetyWorkOrder, WorkOrderFlowLog
from app.schemas.profiles import ProfileRecalculateRequest
from app.schemas.work_orders import WorkOrderStatusUpdate
from app.services.profiles import service as profile_service


def transition_work_order(
    db: Session,
    work_order_id: str,
    payload: WorkOrderStatusUpdate,
    current_user: MockUser,
) -> dict | None:
    query = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == work_order_id)
    query = apply_data_scope(query, SafetyWorkOrder, current_user)
    order = query.first()
    if order is None:
        return None

    assert_work_order_action_allowed(db, current_user, order, payload.action)
    _validate_action_payload(payload)

    from_status = order.status
    next_status = transition_status(WorkOrderStatus(from_status), payload.action)
    now = dt.datetime.now()

    _apply_action_side_effects(db, order, payload, current_user, now)
    order.status = next_status.value

    flow_log = WorkOrderFlowLog(
        work_order_id=order.work_order_id,
        from_status=from_status,
        to_status=next_status.value,
        action=payload.action,
        operator_user_id=current_user.user_id,
        operator_role=current_user.role,
        comment=payload.comment,
        reject_reason=payload.reject_reason,
        attachments=payload.attachments,
    )
    db.add(flow_log)
    db.flush()

    if payload.action == "review_pass" and order.project_id:
        profile_service.recalculate_profiles(
            db,
            ProfileRecalculateRequest(profile_types=["project"], project_id=order.project_id),
            current_user=current_user,
        )

    db.commit()
    db.refresh(order)
    return {
        "work_order_id": order.work_order_id,
        "action": payload.action,
        "new_status": order.status,
    }


def _validate_action_payload(payload: WorkOrderStatusUpdate) -> None:
    if payload.action == "confirm":
        if not payload.assignee_user_id:
            raise ValueError("Assignee user id is required")
        if payload.due_time is None:
            raise ValueError("Due time is required")
    if payload.action == "submit_result" and not _has_rectification_attachment(payload.attachments):
        raise ValueError("At least one rectification image is required")
    if payload.action == "review_reject" and not payload.reject_reason:
        raise ValueError("Reject reason is required")


def _apply_action_side_effects(
    db: Session,
    order: SafetyWorkOrder,
    payload: WorkOrderStatusUpdate,
    current_user: MockUser,
    now: dt.datetime,
) -> None:
    if payload.action == "confirm":
        order.responsible_user_id = payload.assignee_user_id
        order.due_time = payload.due_time
    elif payload.action == "accept":
        order.responsible_user_id = order.responsible_user_id or current_user.user_id
    elif payload.action == "submit_result":
        order.attachments = _merge_attachments(order.attachments, payload.attachments)
    elif payload.action == "review_pass":
        order.review_user_id = current_user.user_id
        order.review_time = now
        order.close_time = now
        _close_related_hazard(db, order, now.date())
    elif payload.action == "review_reject":
        order.review_user_id = current_user.user_id
        order.review_time = now
        order.reject_reason = payload.reject_reason


def _has_rectification_attachment(attachments: dict | None) -> bool:
    if not attachments:
        return False
    return any(item.get("phase") == "rectification" for item in attachments.get("items") or [])


def _merge_attachments(current: dict | None, patch: dict | None) -> dict:
    current_items = list((current or {}).get("items") or [])
    patch_items = list((patch or {}).get("items") or [])
    return {"items": current_items + patch_items}


def _close_related_hazard(db: Session, order: SafetyWorkOrder, close_date: dt.date) -> None:
    hazard = (
        db.query(Hazard)
        .filter(
            Hazard.work_order_id == order.work_order_id,
            Hazard.project_id == order.project_id,
        )
        .first()
    )
    if hazard is None and order.source_type == "hazard" and order.source_id:
        hazard = db.query(Hazard).filter(Hazard.hazard_id == order.source_id).first()
    if hazard is None:
        return
    hazard.status = "closed"
    hazard.close_date = close_date
