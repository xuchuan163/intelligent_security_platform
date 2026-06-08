import time
import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.security import MockUser
from app.infrastructure.database.models import AgentNl2sqlAudit
from app.services.nl2sql.auditor import audit_sql

MAX_RESULT_ROWS = 100
MAX_RESULT_FIELDS = 30
MAX_TEXT_LENGTH = 500


def _truncate_value(value: Any) -> Any:
    if isinstance(value, str) and len(value) > MAX_TEXT_LENGTH:
        return value[:MAX_TEXT_LENGTH]
    return value


def _new_audit_row(
    current_user: MockUser,
    question: str,
    candidate_sql: str,
    audit_result,
) -> AgentNl2sqlAudit:
    return AgentNl2sqlAudit(
        audit_id=f"NLSQL-{uuid.uuid4().hex[:16]}",
        tenant_id=current_user.tenant_id,
        org_path=current_user.org_path,
        user_id=current_user.user_id,
        question=question,
        candidate_sql=candidate_sql,
        sanitized_sql=audit_result.sanitized_sql,
        allowed=audit_result.allowed,
        reject_reason=audit_result.reject_reason,
        tables_used=audit_result.tables_used,
        fields_used=audit_result.fields_used,
        scope_injected=audit_result.scope_injected,
        execution_status="audited",
        result_row_count=0,
        result_field_count=0,
    )


def _result_payload(audit_row: AgentNl2sqlAudit, rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    return {
        "allowed": audit_row.allowed,
        "audit_id": audit_row.audit_id,
        "sanitized_sql": audit_row.sanitized_sql,
        "execution_status": audit_row.execution_status,
        "row_count": audit_row.result_row_count,
        "field_count": audit_row.result_field_count,
        "columns": columns,
        "rows": rows,
        "execution_error": audit_row.execution_error,
    }


def execute_readonly_sql(
    db: Session,
    question: str,
    candidate_sql: str,
    current_user: MockUser,
) -> dict[str, Any]:
    start = time.perf_counter()
    audit_result = audit_sql(candidate_sql, current_user)
    audit_row = _new_audit_row(current_user, question, candidate_sql, audit_result)
    db.add(audit_row)
    db.flush()

    if not audit_result.allowed or audit_result.sanitized_sql is None:
        audit_row.execution_status = "rejected"
        audit_row.elapsed_ms = int((time.perf_counter() - start) * 1000)
        db.commit()
        return _result_payload(audit_row, [], [])

    try:
        result = db.execute(text(audit_result.sanitized_sql))
        columns = list(result.keys())[:MAX_RESULT_FIELDS]
        rows: list[dict[str, Any]] = []
        for row in result.mappings():
            rows.append({column: _truncate_value(row[column]) for column in columns})
            if len(rows) >= MAX_RESULT_ROWS:
                break

        audit_row.execution_status = "executed"
        audit_row.result_row_count = len(rows)
        audit_row.result_field_count = len(columns)
        audit_row.elapsed_ms = int((time.perf_counter() - start) * 1000)
        db.commit()
        return _result_payload(audit_row, rows, columns)
    except SQLAlchemyError as exc:
        audit_row.execution_status = "failed"
        audit_row.execution_error = str(exc)[:MAX_TEXT_LENGTH]
        audit_row.result_row_count = 0
        audit_row.result_field_count = 0
        audit_row.elapsed_ms = int((time.perf_counter() - start) * 1000)
        db.commit()
        return _result_payload(audit_row, [], [])
