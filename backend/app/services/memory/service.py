import datetime as dt
import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import DataScope, MockUser
from app.infrastructure.database.models import AgentSessionSummary, AgentTaskCheckpoint
from app.infrastructure.redis_client import RedisLike
from app.services.memory.context_resolver import merge_session_context

MEMORY_TTL_SECONDS = settings.memory_session_ttl_seconds

BLOCKED_CONTEXT_KEYS = {
    "full_sql_result",
    "raw_sql_result",
    "sql_result",
    "sql_results",
    "query_result",
    "rows",
    "dataframe",
    "identity_card",
    "id_card",
    "id_card_no",
    "health_detail",
    "health_details",
    "face_image",
    "raw_video",
}


def sanitize_memory_payload(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, item in value.items():
            if str(key).lower() in BLOCKED_CONTEXT_KEYS:
                continue
            cleaned[key] = sanitize_memory_payload(item)
        return cleaned
    if isinstance(value, list):
        return [sanitize_memory_payload(item) for item in value]
    return value


def session_memory_key(user_id: str, session_id: str) -> str:
    return f"session:{user_id}:{session_id}"


def checkpoint_key(user_id: str, task_id: str) -> str:
    return f"checkpoint:{user_id}:{task_id}"


def _now() -> dt.datetime:
    return dt.datetime.utcnow()


def _json_default(value: Any) -> str:
    if isinstance(value, (dt.datetime, dt.date)):
        return value.isoformat()
    return str(value)


def _decode_json(value: str | bytes | None) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return json.loads(value)


def _scope_query(db: Session, current_user: MockUser, session_id: str):
    query = db.query(AgentSessionSummary).filter(
        AgentSessionSummary.tenant_id == current_user.tenant_id,
        AgentSessionSummary.user_id == current_user.user_id,
        AgentSessionSummary.session_id == session_id,
    )
    if current_user.data_scope == DataScope.ORG:
        query = query.filter(AgentSessionSummary.org_path.like(f"{current_user.org_path}%"))
    return query


def append_session_memory(
    db: Session,
    redis_client: RedisLike,
    current_user: MockUser,
    session_id: str,
    message: dict[str, Any],
    context: dict[str, Any] | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    key = session_memory_key(current_user.user_id, session_id)
    cached = _decode_json(redis_client.get(key))
    messages = list(cached.get("messages", [])) if cached else []
    messages.append(sanitize_memory_payload(message))
    previous_context = cached.get("context", {}) if cached else {}
    merged_context = merge_session_context(previous_context, context or {})
    preserved_summary = summary if summary is not None else (cached.get("summary") if cached else None)

    now = _now()
    data = {
        "session_id": session_id,
        "user_id": current_user.user_id,
        "tenant_id": current_user.tenant_id,
        "messages": messages[-20:],
        "context": sanitize_memory_payload(merged_context),
        "summary": preserved_summary,
        "message_count": len(messages),
        "store_full_sql_result": False,
        "updated_at": now.isoformat(),
        "source": "redis",
    }
    redis_client.setex(key, MEMORY_TTL_SECONDS, json.dumps(data, ensure_ascii=False, default=_json_default))

    row = _scope_query(db, current_user, session_id).one_or_none()
    if row is None:
        row = AgentSessionSummary(
            tenant_id=current_user.tenant_id,
            org_path=current_user.org_path,
            user_id=current_user.user_id,
            session_id=session_id,
            summary=summary,
            message_count=len(messages),
            last_message_at=now,
        )
        db.add(row)
    else:
        row.summary = summary if summary is not None else row.summary
        row.message_count = len(messages)
        row.last_message_at = now
    db.commit()
    return data


def get_session_memory(
    db: Session,
    redis_client: RedisLike,
    current_user: MockUser,
    session_id: str,
) -> dict[str, Any] | None:
    cached = _decode_json(redis_client.get(session_memory_key(current_user.user_id, session_id)))
    if cached is not None:
        cached["store_full_sql_result"] = False
        cached["source"] = "redis"
        return cached

    row = _scope_query(db, current_user, session_id).one_or_none()
    if row is None:
        return None
    return {
        "session_id": row.session_id,
        "user_id": row.user_id,
        "tenant_id": row.tenant_id,
        "messages": [],
        "context": {},
        "summary": row.summary,
        "message_count": row.message_count,
        "store_full_sql_result": False,
        "source": "mysql_summary",
    }


def save_task_checkpoint(
    db: Session,
    redis_client: RedisLike,
    current_user: MockUser,
    task_id: str,
    task_type: str | None,
    status: str,
    context: dict[str, Any] | None = None,
    sub_tasks: list[dict[str, Any]] | None = None,
    result_ref: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    now = _now()
    sanitized_context = sanitize_memory_payload(context or {})
    data = {
        "task_id": task_id,
        "tenant_id": current_user.tenant_id,
        "user_id": current_user.user_id,
        "task_type": task_type,
        "status": status,
        "context": sanitized_context,
        "sub_tasks": sanitize_memory_payload(sub_tasks or []),
        "result_ref": result_ref,
        "error_message": error_message,
        "updated_at": now.isoformat(),
    }
    redis_client.setex(
        checkpoint_key(current_user.user_id, task_id),
        MEMORY_TTL_SECONDS,
        json.dumps(data, ensure_ascii=False, default=_json_default),
    )

    row = db.query(AgentTaskCheckpoint).filter(
        AgentTaskCheckpoint.tenant_id == current_user.tenant_id,
        AgentTaskCheckpoint.task_id == task_id,
    ).one_or_none()
    if row is None:
        row = AgentTaskCheckpoint(
            task_id=task_id,
            tenant_id=current_user.tenant_id,
            org_path=current_user.org_path,
            user_id=current_user.user_id,
            task_type=task_type,
            status=status,
            context_json=sanitized_context,
            sub_task_json=data["sub_tasks"],
            result_ref=result_ref,
            error_message=error_message,
        )
        db.add(row)
    else:
        row.status = status
        row.context_json = sanitized_context
        row.sub_task_json = data["sub_tasks"]
        row.result_ref = result_ref
        row.error_message = error_message
    db.commit()
    return data
