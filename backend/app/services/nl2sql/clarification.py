from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import AgentTaskCheckpoint


CLARIFICATION_TASK_TYPE = "nl2sql_clarification"
STATUS_AWAITING = "awaiting_clarification"
STATUS_RESOLVED = "resolved"
MAX_CLARIFICATION_TURNS = 3


class ClarificationSessionError(ValueError):
    pass


class ClarificationAccessError(PermissionError):
    pass


def compose_refined_question(
    *,
    original_question: str,
    clarification_prompt: str,
    replies: list[str],
) -> str:
    lines = [
        f"Original question: {original_question}",
        f"Clarification needed: {clarification_prompt}",
    ]
    for index, reply in enumerate(replies, start=1):
        lines.append(f"User clarification {index}: {reply}")
    lines.append("Generate SQL for the clarified business question above.")
    return "\n".join(lines)


def build_clarification_context(
    *,
    original_question: str,
    clarification_prompt: str,
    replies: list[str],
) -> dict[str, Any]:
    return {
        "original_question": original_question,
        "clarification_prompt": clarification_prompt,
        "replies": replies,
        "refined_question": compose_refined_question(
            original_question=original_question,
            clarification_prompt=clarification_prompt,
            replies=replies,
        ),
    }


def create_clarification_session(
    db: Session,
    *,
    current_user: MockUser,
    original_question: str,
    clarification_prompt: str,
    audit_id: str | None = None,
) -> dict[str, Any]:
    clarification_id = f"NL2SQL-CLR-{uuid.uuid4().hex[:16]}"
    context = {
        "original_question": original_question,
        "clarification_prompt": clarification_prompt,
        "replies": [],
        "audit_id": audit_id,
        "turn": 1,
    }
    row = AgentTaskCheckpoint(
        task_id=clarification_id,
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        org_path=current_user.org_path,
        user_id=current_user.user_id,
        task_type=CLARIFICATION_TASK_TYPE,
        status=STATUS_AWAITING,
        context_json=context,
        sub_task_json=[],
        result_ref=audit_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return clarification_session_to_dict(row)


def get_clarification_session(
    db: Session,
    *,
    current_user: MockUser,
    clarification_id: str,
) -> AgentTaskCheckpoint | None:
    query = apply_data_scope(
        db.query(AgentTaskCheckpoint).filter(AgentTaskCheckpoint.task_id == clarification_id),
        AgentTaskCheckpoint,
        current_user,
    )
    row = query.one_or_none()
    if row is None:
        return None
    if row.user_id != current_user.user_id:
        raise ClarificationAccessError("Clarification session belongs to another user")
    if row.task_type != CLARIFICATION_TASK_TYPE:
        raise ClarificationSessionError("Task is not an NL2SQL clarification session")
    return row


def append_clarification_reply(
    db: Session,
    *,
    current_user: MockUser,
    clarification_id: str,
    reply: str,
) -> dict[str, Any]:
    row = get_clarification_session(db, current_user=current_user, clarification_id=clarification_id)
    if row is None:
        raise ClarificationSessionError("Clarification session not found")
    if row.status != STATUS_AWAITING:
        raise ClarificationSessionError("Clarification session is no longer awaiting input")

    context = dict(row.context_json or {})
    replies = list(context.get("replies") or [])
    if len(replies) >= MAX_CLARIFICATION_TURNS:
        raise ClarificationSessionError("Maximum clarification turns reached")

    replies.append({"text": reply.strip(), "at": dt.datetime.utcnow().isoformat()})
    context["replies"] = replies
    context["turn"] = len(replies) + 1
    row.context_json = context
    db.commit()
    db.refresh(row)
    return clarification_session_to_dict(row)


def resolve_clarification_session(
    db: Session,
    *,
    current_user: MockUser,
    clarification_id: str,
    result_ref: str | None = None,
) -> dict[str, Any]:
    row = get_clarification_session(db, current_user=current_user, clarification_id=clarification_id)
    if row is None:
        raise ClarificationSessionError("Clarification session not found")
    row.status = STATUS_RESOLVED
    if result_ref:
        row.result_ref = result_ref
    db.commit()
    db.refresh(row)
    return clarification_session_to_dict(row)


def clarification_session_to_dict(row: AgentTaskCheckpoint) -> dict[str, Any]:
    context = row.context_json or {}
    reply_texts = [item["text"] for item in context.get("replies", []) if isinstance(item, dict) and item.get("text")]
    return {
        "clarification_id": row.task_id,
        "status": row.status,
        "original_question": context.get("original_question"),
        "clarification_prompt": context.get("clarification_prompt"),
        "replies": context.get("replies") or [],
        "turn": context.get("turn", 1),
        "refined_question": compose_refined_question(
            original_question=str(context.get("original_question") or ""),
            clarification_prompt=str(context.get("clarification_prompt") or ""),
            replies=reply_texts,
        )
        if context.get("original_question")
        else None,
        "audit_id": context.get("audit_id") or row.result_ref,
    }
