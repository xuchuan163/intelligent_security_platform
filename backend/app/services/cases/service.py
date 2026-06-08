from sqlalchemy.orm import Session

from app.core.security import MockUser
from app.infrastructure.database.models import AccidentCaseLibrary


def accident_case_to_item(row: AccidentCaseLibrary) -> dict:
    return {
        "accident_case_id": row.accident_case_id,
        "tenant_id": row.tenant_id,
        "accident_type": row.accident_type,
        "severity": row.severity,
        "project_type": row.project_type,
        "operation_scene": row.operation_scene,
        "direct_cause": row.direct_cause,
        "indirect_cause": row.indirect_cause,
        "involved_subjects": row.involved_subjects,
        "warning_indicators": row.warning_indicators,
        "rectification_measures": row.rectification_measures,
        "tags": row.tags,
        "embedding_version": row.embedding_version,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def list_accident_cases(
    db: Session,
    current_user: MockUser,
    page_no: int = 1,
    page_size: int = 20,
    accident_type: str | None = None,
    severity: str | None = None,
    status: str = "active",
) -> dict:
    query = db.query(AccidentCaseLibrary).filter(
        AccidentCaseLibrary.tenant_id == current_user.tenant_id,
    )
    if status:
        query = query.filter(AccidentCaseLibrary.status == status)
    if accident_type:
        query = query.filter(AccidentCaseLibrary.accident_type == accident_type)
    if severity:
        query = query.filter(AccidentCaseLibrary.severity == severity)

    total = query.count()
    rows = (
        query.order_by(AccidentCaseLibrary.created_at.desc(), AccidentCaseLibrary.accident_case_id.asc())
        .offset((page_no - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "page_no": page_no,
        "page_size": page_size,
        "total": total,
        "items": [accident_case_to_item(row) for row in rows],
    }
