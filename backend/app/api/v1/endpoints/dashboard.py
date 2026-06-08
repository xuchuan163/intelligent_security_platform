from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.services.dashboard.service import get_dashboard_overview

router = APIRouter()


@router.get("/overview")
def dashboard_overview(
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.DASHBOARD_READ)),
):
    try:
        return success(get_dashboard_overview(db, current_user=current_user))
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
