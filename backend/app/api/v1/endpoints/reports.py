import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.endpoints._errors import db_guard
from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.services.reports.service import get_project_weekly_report, get_subcontractor_eval_report

router = APIRouter()


@router.get("/project-weekly/{project_id}")
def project_weekly_report(
    project_id: str,
    week_end: dt.date | None = Query(
        None,
        description="Week anchor date (defaults to today); report covers Mon–Sun of that ISO week.",
    ),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.DASHBOARD_READ)),
) -> dict:
    def query() -> dict:
        report = get_project_weekly_report(
            db,
            project_id,
            week_end=week_end,
            current_user=current_user,
        )
        if report is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return report

    return success(db_guard(query))


@router.get("/subcontractor-eval/{subcontractor_id}")
def subcontractor_eval_report(
    subcontractor_id: str,
    project_id: str | None = Query(
        None,
        description="Optional project scope; when set, KPIs are limited to that project.",
    ),
    eval_date: dt.date | None = Query(
        None,
        description="Evaluation anchor date (defaults to today).",
    ),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.DASHBOARD_READ)),
) -> dict:
    def query() -> dict:
        report = get_subcontractor_eval_report(
            db,
            subcontractor_id,
            project_id=project_id,
            eval_date=eval_date,
            current_user=current_user,
        )
        if report is None:
            raise HTTPException(status_code=404, detail="Subcontractor not found")
        return report

    return success(db_guard(query))
