from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.responses import success
from app.infrastructure.database.session import get_db
from app.schemas.work_orders import WorkOrderCreate, WorkOrderStatusUpdate
from app.services.work_orders.service import create_work_order, list_work_orders, update_work_order_status

router = APIRouter()


@router.get("")
def get_work_orders(
    project_id: str | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> dict:
    try:
        return success(list_work_orders(db, project_id, status))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("")
def post_work_order(body: WorkOrderCreate, db: Session = Depends(get_db)) -> dict:
    try:
        order = create_work_order(db, body)
        return success({"work_order_id": order.work_order_id})
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.patch("/{work_order_id}/status")
def change_work_order_status(
    work_order_id: str,
    body: WorkOrderStatusUpdate,
    db: Session = Depends(get_db),
) -> dict:
    result = update_work_order_status(db, work_order_id, body.action)
    if result is None:
        raise HTTPException(status_code=404, detail="Work order not found")
    if "error" in result:
        raise HTTPException(status_code=409, detail=result["error"])
    return success(result)
