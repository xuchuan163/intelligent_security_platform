from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.schemas.agent import (
    AgentApprovalDecisionRequest,
    AgentAskRequest,
    AgentFeedbackCreateRequest,
    AgentPromptActivateRequest,
)
from app.schemas.nl2sql import Nl2SqlQueryRequest
from app.services.agents.approval_queue import (
    approval_to_dict,
    decide_approval_request,
    execute_approved_request,
    get_approval_request,
    list_approval_requests,
)
from app.infrastructure.redis_client import RedisLike, build_redis_client_optional
from app.services.agents.dag_executor import execute_agent_dag
from app.services.agents.feedback import create_agent_feedback, list_agent_feedback
from app.services.agents.prompt_registry import (
    activate_prompt_version,
    list_prompt_versions,
    prompt_version_to_dict,
    sync_agent_prompt_versions,
)
from app.services.agents.router import route_agent_message
from app.services.memory.agent_bridge import (
    prepare_request_context,
    record_agent_interaction,
    record_nl2sql_interaction,
)
from app.services.nl2sql.api_service import run_nl2sql_query

router = APIRouter()


def get_redis_client_optional() -> RedisLike | None:
    return build_redis_client_optional()


@router.get("/prompts")
def get_agent_prompts(
    agent_code: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AUTH_ADMIN)),
) -> dict:
    _ = current_user
    rows = list_prompt_versions(db, agent_code=agent_code)
    return success(
        {
            "items": [prompt_version_to_dict(row) for row in rows],
            "total": len(rows),
        }
    )


@router.post("/prompts/sync")
def sync_agent_prompts(
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AUTH_ADMIN)),
) -> dict:
    _ = current_user
    return success(sync_agent_prompt_versions(db))


@router.post("/prompts/{agent_code}/activate")
def activate_agent_prompt(
    agent_code: str,
    body: AgentPromptActivateRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AUTH_ADMIN)),
) -> dict:
    _ = current_user
    try:
        row = activate_prompt_version(db, agent_code=agent_code, prompt_version=body.prompt_version)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return success(prompt_version_to_dict(row))


@router.get("/approvals")
def get_agent_approvals(
    status: str | None = Query("pending"),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    return success(list_approval_requests(db, current_user=current_user, status=status))


@router.get("/approvals/{approval_id}")
def get_agent_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    approval = get_approval_request(db, approval_id=approval_id, current_user=current_user)
    if approval is None:
        raise HTTPException(status_code=404, detail="Agent approval request not found")
    return success(approval_to_dict(approval))


@router.post("/approvals/{approval_id}/approve")
def approve_agent_approval(
    approval_id: str,
    body: AgentApprovalDecisionRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    return _decide_agent_approval(db, approval_id, current_user, "approved", body.comment)


@router.post("/approvals/{approval_id}/reject")
def reject_agent_approval(
    approval_id: str,
    body: AgentApprovalDecisionRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    return _decide_agent_approval(db, approval_id, current_user, "rejected", body.comment)


@router.post("/approvals/{approval_id}/execute")
def execute_agent_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    try:
        result = execute_approved_request(db, approval_id=approval_id, current_user=current_user)
        if result is None:
            raise HTTPException(status_code=404, detail="Agent approval request not found")
        return success(result)
    except HTTPException:
        raise
    except PermissionError as exc:
        db.rollback()
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/nl2sql")
def post_nl2sql(
    body: Nl2SqlQueryRequest,
    db: Session = Depends(get_db),
    redis_client: RedisLike | None = Depends(get_redis_client_optional),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_ASK)),
) -> dict:
    try:
        merged_context, _memory = prepare_request_context(
            db,
            redis_client,
            current_user=current_user,
            session_id=body.session_id,
            incoming_context=None,
        )
        result = run_nl2sql_query(db, body, current_user, redis_client=redis_client, merged_context=merged_context)
        record_nl2sql_interaction(
            db,
            redis_client,
            current_user=current_user,
            session_id=body.session_id,
            question=result.get("question") or body.question,
            result=result,
            merged_context=merged_context,
        )
        if body.session_id:
            result["session_id"] = body.session_id
        return success(result)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/feedback")
def get_agent_feedback(
    agent_name: str | None = Query(None),
    feedback_type: str | None = Query(None),
    task_id: str | None = Query(None),
    label_status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_ASK)),
) -> dict:
    return success(
        list_agent_feedback(
            db,
            current_user=current_user,
            agent_name=agent_name,
            feedback_type=feedback_type,
            task_id=task_id,
            label_status=label_status,
            limit=limit,
        )
    )


@router.post("/feedback")
def post_agent_feedback(
    body: AgentFeedbackCreateRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_ASK)),
) -> dict:
    try:
        return success(
            create_agent_feedback(
                db,
                current_user=current_user,
                task_id=body.task_id,
                agent_name=body.agent_name,
                feedback_type=body.feedback_type,
                rating=body.rating,
                feedback_reason=body.feedback_reason,
                original_output=body.original_output,
                corrected_output=body.corrected_output,
                correction_text=body.correction_text,
                related_work_order_id=body.related_work_order_id,
                project_id=body.project_id,
            )
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/ask")
def post_agent_ask(
    body: AgentAskRequest,
    db: Session = Depends(get_db),
    redis_client: RedisLike | None = Depends(get_redis_client_optional),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_ASK)),
) -> dict:
    merged_context, memory = prepare_request_context(
        db,
        redis_client,
        current_user=current_user,
        session_id=body.session_id,
        incoming_context=body.context,
    )
    if body.execution_mode in {"dry_run", "controlled_execute"}:
        route_result = route_agent_message(db, body.message, merged_context, "plan_only")
        result = execute_agent_dag(
            db,
            route_result=route_result,
            message=body.message,
            context=merged_context,
            current_user=current_user,
            execution_mode=body.execution_mode,
        )
    else:
        result = route_agent_message(db, body.message, merged_context, body.execution_mode)

    record_agent_interaction(
        db,
        redis_client,
        current_user=current_user,
        session_id=body.session_id,
        user_message=body.message,
        result=result,
        merged_context=merged_context,
    )
    if body.session_id:
        result["session_id"] = body.session_id
    if memory is not None:
        result["memory_source"] = memory.get("source")
    return success(result)


def _decide_agent_approval(
    db: Session,
    approval_id: str,
    current_user: MockUser,
    decision: str,
    comment: str | None,
) -> dict:
    try:
        result = decide_approval_request(
            db,
            approval_id=approval_id,
            current_user=current_user,
            decision=decision,  # type: ignore[arg-type]
            comment=comment,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Agent approval request not found")
        return success(result)
    except HTTPException:
        raise
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
