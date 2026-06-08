from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import RuleTriggerLog


RULE_NAMES = {
    "SR-PROJ-001": "重大隐患超期未闭环",
    "SR-PROJ-004": "特种设备超期未检",
    "SR-WORKER-001": "特种作业证异常",
    "SR-WORKER-005": "频繁违规",
}


def list_rule_triggers(
    db: Session,
    current_user: MockUser | None = None,
    *,
    project_id: str | None = None,
    rule_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    query = db.query(RuleTriggerLog)
    if current_user:
        query = apply_data_scope(query, RuleTriggerLog, current_user)
    if project_id:
        query = query.filter(RuleTriggerLog.project_id == project_id)
    if rule_id:
        query = query.filter(RuleTriggerLog.rule_id == rule_id)

    rows = query.order_by(RuleTriggerLog.created_at.desc()).limit(limit).all()
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
