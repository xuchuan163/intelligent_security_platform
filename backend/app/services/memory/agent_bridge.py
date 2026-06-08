from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.core.security import MockUser
from app.infrastructure.redis_client import RedisLike
from app.services.memory.context_resolver import merge_session_context, resolve_follow_up_context
from app.services.memory.service import append_session_memory, get_session_memory

PRONOUN_MARKERS = ("它", "这个", "上次", "继续", "同上", "前述", "该", "this", "same", "previous")


def prepare_request_context(
    db: Session,
    redis_client: RedisLike | None,
    *,
    current_user: MockUser,
    session_id: str | None,
    incoming_context: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if not session_id or redis_client is None:
        return dict(incoming_context or {}), None

    memory = get_session_memory(db, redis_client, current_user=current_user, session_id=session_id)
    if memory is None:
        return dict(incoming_context or {}), None

    resolved = resolve_follow_up_context(memory)
    merged = merge_session_context(resolved, incoming_context or {})
    return merged, memory


def record_agent_interaction(
    db: Session,
    redis_client: RedisLike | None,
    *,
    current_user: MockUser,
    session_id: str | None,
    user_message: str,
    result: dict[str, Any],
    merged_context: dict[str, Any],
) -> None:
    if not session_id or redis_client is None:
        return

    assistant_context = dict(merged_context)
    assistant_context.update(
        {
            "last_target_agent": result.get("target_agent"),
            "last_intent": result.get("intent"),
            "last_execution_mode": result.get("execution_mode"),
        }
    )
    if result.get("run_id"):
        assistant_context["last_run_id"] = result["run_id"]

    append_session_memory(
        db,
        redis_client,
        current_user=current_user,
        session_id=session_id,
        message={"role": "user", "content": user_message},
        context=merged_context,
    )
    append_session_memory(
        db,
        redis_client,
        current_user=current_user,
        session_id=session_id,
        message={
            "role": "assistant",
            "content": _agent_summary(result),
        },
        context=assistant_context,
        summary=_agent_summary(result),
    )


def enrich_nl2sql_question(question: str, memory: dict[str, Any] | None) -> str:
    if not memory:
        return question
    normalized = question.strip()
    if not normalized:
        return question

    resolved = resolve_follow_up_context(memory, follow_up_message=normalized)
    project_id = resolved.get("project_id")
    if project_id and project_id not in normalized and _contains_pronoun_marker(normalized):
        return f"{normalized} (context: project_id={project_id})"
    return question


def record_nl2sql_interaction(
    db: Session,
    redis_client: RedisLike | None,
    *,
    current_user: MockUser,
    session_id: str | None,
    question: str,
    result: dict[str, Any],
    merged_context: dict[str, Any],
) -> None:
    if not session_id or redis_client is None:
        return

    assistant_context = dict(merged_context)
    assistant_context.update(
        {
            "last_question": question,
            "last_audit_id": result.get("audit_id"),
            "last_nl2sql_status": result.get("status"),
            "last_execution_status": result.get("execution_status"),
        }
    )
    if result.get("clarification_id"):
        assistant_context["last_clarification_id"] = result["clarification_id"]

    append_session_memory(
        db,
        redis_client,
        current_user=current_user,
        session_id=session_id,
        message={"role": "user", "content": question},
        context=merged_context,
    )
    append_session_memory(
        db,
        redis_client,
        current_user=current_user,
        session_id=session_id,
        message={"role": "assistant", "content": _nl2sql_summary(result)},
        context=assistant_context,
        summary=_nl2sql_summary(result),
    )


def _contains_pronoun_marker(text: str) -> bool:
    lowered = text.lower()
    return any(marker in text or marker in lowered for marker in PRONOUN_MARKERS)


def _agent_summary(result: dict[str, Any]) -> str:
    agent = result.get("target_agent") or "agent"
    intent = result.get("intent") or "unknown"
    mode = result.get("execution_mode") or "route_only"
    return f"{agent} handled {intent} via {mode}"


def _nl2sql_summary(result: dict[str, Any]) -> str:
    status = result.get("status") or "unknown"
    audit_id = result.get("audit_id") or "n/a"
    return f"nl2sql {status} audit={audit_id}"
