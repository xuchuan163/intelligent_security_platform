from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.schemas.metrics import MetricValidateRequest
from app.services.metrics.service import (
    get_metric_detail,
    get_metric_lineage,
    list_metric_aliases,
    list_metric_catalog,
    validate_metric_contract,
)

router = APIRouter()


@router.get("/catalog")
def metric_catalog(
    page_no: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.METRICS_READ)),
) -> dict:
    try:
        _ = current_user
        return success(list_metric_catalog(db, page_no, page_size, status, keyword))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.post("/validate")
def metric_validate(
    body: MetricValidateRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.METRICS_READ)),
) -> dict:
    try:
        _ = current_user
        return success(validate_metric_contract(db, body.metric_codes))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.get("/lineage/{metric_code}")
def metric_lineage(
    metric_code: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.METRICS_READ)),
) -> dict:
    try:
        _ = current_user
        lineage = get_metric_lineage(db, metric_code)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    if lineage is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return success(lineage)


@router.get("/aliases")
def metric_aliases(
    keyword: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.METRICS_READ)),
) -> dict:
    try:
        _ = current_user
        return success(list_metric_aliases(db, keyword))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc


@router.get("/{metric_code}")
def metric_detail(
    metric_code: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.METRICS_READ)),
) -> dict:
    try:
        _ = current_user
        metric = get_metric_detail(db, metric_code)
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc

    if metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return success(metric)
