from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.endpoints._errors import db_guard
from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.services.rules.service import list_rule_triggers

router = APIRouter()


@router.get("/triggers")
def rule_triggers(
    project_id: str | None = Query(None, description="Filter by project_id"),
    rule_id: str | None = Query(None, description="Filter by strong rule_id"),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.RULES_READ)),
) -> dict:
    def query() -> list[dict]:
        return list_rule_triggers(
            db,
            current_user=current_user,
            project_id=project_id,
            rule_id=rule_id,
        )

    return success(db_guard(query))
