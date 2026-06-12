from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.schemas.profiles import ProfileRecalculateRequest
from app.services.profiles.service import (
    get_project_profile,
    get_project_ranking,
    get_subcontractor_profile,
    get_worker_profile,
    list_workers,
    recalculate_profiles as recalculate_profile_service,
)

router = APIRouter()


@router.get("/project/{project_id}")
def project_profile(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_READ)),
):
    try:
        data = get_project_profile(db, project_id, current_user=current_user)
        if data is None:
            raise HTTPException(status_code=404, detail="Project profile not found")
        return success(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/workers")
def workers_index(
    project_id: str | None = Query(None, description="Optional project scope filter"),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_READ)),
):
    try:
        items = list_workers(db, project_id=project_id, limit=limit, current_user=current_user)
        return success({"items": items, "total": len(items)})
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/worker/{worker_id}")
def worker_profile(
    worker_id: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_READ)),
):
    try:
        data = get_worker_profile(db, worker_id, current_user=current_user)
        if data is None:
            raise HTTPException(status_code=404, detail="Worker profile not found")
        return success(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/subcontractor/{subcontractor_id}")
def subcontractor_profile(
    subcontractor_id: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_READ)),
):
    try:
        data = get_subcontractor_profile(db, subcontractor_id, current_user=current_user)
        if data is None:
            raise HTTPException(status_code=404, detail="Subcontractor profile not found")
        return success(data)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/ranking/projects")
def project_ranking(
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_READ)),
):
    try:
        data = get_project_ranking(db, current_user=current_user)
        return success(data)
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/recalculate")
def recalculate_profiles(
    body: ProfileRecalculateRequest | None = None,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_RECALCULATE)),
):
    try:
        return success(recalculate_profile_service(db, body, current_user))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(e))
