from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.services.projects.service import list_accessible_projects

router = APIRouter()


@router.get("")
def get_projects(
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.PROFILE_READ)),
) -> dict:
    try:
        items = list_accessible_projects(db, current_user=current_user)
        return success({"items": items})
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
