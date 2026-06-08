from __future__ import annotations

import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import AgentFeedback

FeedbackType = Literal["thumb", "rating", "correction", "adoption"]


def create_agent_feedback(
    db: Session,
    *,
    current_user: MockUser,
    task_id: str,
    agent_name: str,
    feedback_type: FeedbackType,
    rating: int | None = None,
    feedback_reason: str | None = None,
    original_output: dict[str, Any] | None = None,
    corrected_output: dict[str, Any] | None = None,
    correction_text: str | None = None,
    related_work_order_id: str | None = None,
    project_id: str | None = None,
) -> dict[str, Any]:
    _validate_feedback_payload(
        feedback_type=feedback_type,
        rating=rating,
        correction_text=correction_text,
        corrected_output=corrected_output,
    )

    row = AgentFeedback(
        feedback_id=f"AGFB-{uuid.uuid4().hex[:16]}",
        task_id=task_id,
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        org_path=current_user.org_path,
        project_id=project_id,
        user_id=current_user.user_id,
        agent_name=agent_name,
        feedback_type=feedback_type,
        rating=rating,
        feedback_reason=feedback_reason,
        original_output=original_output,
        corrected_output=corrected_output,
        correction_text=correction_text,
        related_work_order_id=related_work_order_id,
        label_status="pending",
        used_for_prompt_tuning=False,
        used_for_finetune=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return feedback_to_dict(row)


def list_agent_feedback(
    db: Session,
    *,
    current_user: MockUser,
    agent_name: str | None = None,
    feedback_type: str | None = None,
    task_id: str | None = None,
    label_status: str | None = None,
    limit: int = 50,
) -> dict[str, Any]:
    query = apply_data_scope(db.query(AgentFeedback), AgentFeedback, current_user)
    if agent_name:
        query = query.filter(AgentFeedback.agent_name == agent_name)
    if feedback_type:
        query = query.filter(AgentFeedback.feedback_type == feedback_type)
    if task_id:
        query = query.filter(AgentFeedback.task_id == task_id)
    if label_status:
        query = query.filter(AgentFeedback.label_status == label_status)
    rows = query.order_by(AgentFeedback.created_at.desc(), AgentFeedback.id.desc()).limit(limit).all()
    return {"items": [feedback_to_dict(row) for row in rows], "total": len(rows)}


def feedback_to_dict(row: AgentFeedback) -> dict[str, Any]:
    return {
        "feedback_id": row.feedback_id,
        "task_id": row.task_id,
        "company_id": row.company_id,
        "project_id": row.project_id,
        "user_id": row.user_id,
        "agent_name": row.agent_name,
        "feedback_type": row.feedback_type,
        "rating": row.rating,
        "feedback_reason": row.feedback_reason,
        "original_output": row.original_output,
        "corrected_output": row.corrected_output,
        "correction_text": row.correction_text,
        "related_work_order_id": row.related_work_order_id,
        "label_status": row.label_status,
        "used_for_prompt_tuning": row.used_for_prompt_tuning,
        "used_for_finetune": row.used_for_finetune,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _validate_feedback_payload(
    *,
    feedback_type: FeedbackType,
    rating: int | None,
    correction_text: str | None,
    corrected_output: dict[str, Any] | None,
) -> None:
    if feedback_type == "thumb":
        if rating not in {1, -1}:
            raise ValueError("thumb feedback requires rating 1 or -1")
        return
    if feedback_type == "rating":
        if rating is None or rating < 1 or rating > 5:
            raise ValueError("rating feedback requires rating between 1 and 5")
        return
    if feedback_type == "correction":
        if not correction_text and not corrected_output:
            raise ValueError("correction feedback requires correction_text or corrected_output")
        return
    if feedback_type == "adoption":
        return
    raise ValueError(f"unsupported feedback_type: {feedback_type}")
