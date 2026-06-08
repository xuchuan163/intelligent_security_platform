from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.services.cases.service import list_accident_cases

router = APIRouter()


@router.get("/list")
def case_list(
    page_no: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    accident_type: str | None = Query(None),
    severity: str | None = Query(None),
    status: str = Query("active"),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.RULES_READ)),
) -> dict:
    try:
        return success(
            list_accident_cases(
                db,
                current_user=current_user,
                page_no=page_no,
                page_size=page_size,
                accident_type=accident_type,
                severity=severity,
                status=status,
            )
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
