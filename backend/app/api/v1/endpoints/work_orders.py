import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.v1.endpoints.hazards import _parse_multipart_request
from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser, apply_data_scope
from app.domain.rbac import Permission
from app.infrastructure.database.models import SafetyWorkOrder
from app.infrastructure.database.session import get_db
from app.infrastructure.storage.local_files import save_image
from app.schemas.work_orders import WorkOrderCreate, WorkOrderStatusUpdate
from app.services.work_orders.service import (
    create_work_order,
    escalate_overdue_work_orders,
    get_work_order_detail,
    list_work_orders,
)
from app.services.work_orders.workflow import transition_work_order

router = APIRouter()


@router.get("")
def get_work_orders(
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.WORK_ORDERS_READ)),
) -> dict:
    try:
        return success(list_work_orders(db, project_id, status, current_user))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("")
def post_work_order(
    body: WorkOrderCreate,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.WORK_ORDERS_WRITE)),
) -> dict:
    try:
        order = create_work_order(db, body, current_user)
        return success({"work_order_id": order.work_order_id})
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/{work_order_id}")
def get_work_order(
    work_order_id: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.WORK_ORDERS_READ)),
) -> dict:
    try:
        detail = get_work_order_detail(db, work_order_id, current_user)
        if detail is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        return success(detail)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/escalate-overdue")
def post_escalate_overdue_work_orders(
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.WORK_ORDERS_WRITE)),
) -> dict:
    try:
        return success(escalate_overdue_work_orders(db, current_user))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/{work_order_id}/status")
async def change_work_order_status(
    work_order_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.WORK_ORDERS_WRITE)),
) -> dict:
    try:
        body = await _status_payload_from_request(request, db, work_order_id, current_user)
        result = transition_work_order(db, work_order_id, body, current_user)
        if result is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        return success(result)
    except HTTPException:
        raise
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        status_code = 409 if str(exc).startswith("Invalid work-order transition") else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


async def _status_payload_from_request(
    request: Request,
    db: Session,
    work_order_id: str,
    current_user: MockUser,
) -> WorkOrderStatusUpdate:
    content_type = request.headers.get("content-type") or ""
    if "multipart/form-data" not in content_type:
        return WorkOrderStatusUpdate.model_validate(await request.json())

    fields, images = await _parse_multipart_request(request)
    action = fields.get("action")
    if not action:
        raise ValueError("action is required")

    attachments = None
    if images:
        order = apply_data_scope(
            db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == work_order_id),
            SafetyWorkOrder,
            current_user,
        ).first()
        if order is None:
            raise HTTPException(status_code=404, detail="Work order not found")
        phase = "rectification" if action == "submit_result" else "review"
        attachments = {
            "items": [
                save_image(
                    image,
                    tenant_id=current_user.tenant_id,
                    project_id=order.project_id or "UNKNOWN",
                    uploaded_by=current_user.user_id,
                    phase=phase,
                )
                for image in images
            ]
        }

    return WorkOrderStatusUpdate(
        action=action,
        comment=fields.get("comment"),
        assignee_user_id=fields.get("assignee_user_id"),
        due_time=_parse_optional_datetime(fields.get("due_time")),
        reject_reason=fields.get("reject_reason"),
        attachments=attachments,
    )


def _parse_optional_datetime(value: str | None):
    if not value:
        return None
    return dt.datetime.fromisoformat(value)
