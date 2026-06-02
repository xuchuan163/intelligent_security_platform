from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.endpoints._errors import db_guard
from app.core.responses import success
from app.infrastructure.database.models import RuleTriggerLog
from app.infrastructure.database.session import get_db

router = APIRouter()

RULE_NAMES = {
    "SR-PROJ-001": "重大隐患超期未闭环",
    "SR-PROJ-004": "特种设备超期未检",
    "SR-WORKER-001": "特种作业证异常",
    "SR-WORKER-005": "频繁违规",
}


@router.get("/triggers")
def rule_triggers(db: Session = Depends(get_db)) -> dict:
    def query() -> list[dict]:
        rows = db.query(RuleTriggerLog).order_by(RuleTriggerLog.created_at.desc()).limit(50).all()
        return [
            {
                "trigger_id": f"RT-{row.id:06d}",
                "project_id": row.project_id,
                "object_type": row.object_type,
                "object_id": row.object_id,
                "rule_id": row.rule_id,
                "rule_name": RULE_NAMES.get(row.rule_id, row.rule_id),
                "severity": row.severity,
                "evidence": row.evidence,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    return success(db_guard(query))
