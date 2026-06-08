import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import MockUser
from app.infrastructure.database.models import AgentNl2sqlAudit
from app.infrastructure.cache import read_nl2sql_cache, write_nl2sql_cache
from app.infrastructure.redis_client import RedisLike
from app.schemas.nl2sql import Nl2SqlQueryRequest
from app.services.memory.agent_bridge import enrich_nl2sql_question
from app.services.memory.service import get_session_memory
from app.services.nl2sql.clarification import (
    ClarificationAccessError,
    ClarificationSessionError,
    append_clarification_reply,
    build_clarification_context,
    create_clarification_session,
    get_clarification_session,
    resolve_clarification_session,
)
from app.services.nl2sql.executor import execute_readonly_sql
from app.services.nl2sql.generator import CandidateGenerationResult, generate_candidate_sql
from app.services.nl2sql.providers import build_candidate_sql_provider


LOCAL_APP_ENVS = {"local", "test", "development"}


def run_nl2sql_query(
    db: Session,
    body: Nl2SqlQueryRequest,
    current_user: MockUser,
    *,
    redis_client: RedisLike | None = None,
    merged_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _validate_provider_override(body)
    provider = build_candidate_sql_provider(body.provider, mock_output=body.mock_llm_output)

    if body.clarification_id and body.clarification_reply:
        return _run_clarification_follow_up(
            db,
            body,
            current_user,
            provider,
            redis_client=redis_client,
            merged_context=merged_context,
        )

    memory = None
    if body.session_id and redis_client is not None:
        memory = get_session_memory(db, redis_client, current_user=current_user, session_id=body.session_id)
    question = enrich_nl2sql_question(body.question, memory)

    start = time.perf_counter()
    generation = _resolve_generation(
        question,
        current_user,
        provider,
        redis_client=redis_client,
    )

    if generation.status == "clarification_required":
        session = create_clarification_session(
            db,
            current_user=current_user,
            original_question=question,
            clarification_prompt=generation.rejection_reason or "clarification required",
            audit_id=None,
        )
        audit_row = _write_generation_audit_row(db, current_user, generation, start, execution_status=generation.status)
        session_context = session
        session_context["audit_id"] = audit_row.audit_id
        return _response_from_generation(
            generation,
            audit_id=audit_row.audit_id,
            execution_status=audit_row.execution_status,
            clarification_id=session["clarification_id"],
            clarification_prompt=generation.rejection_reason,
            awaiting_clarification=True,
            turn=1,
            refined_question=None,
        )

    if generation.status != "audit_passed":
        audit_row = _write_generation_audit_row(db, current_user, generation, start, execution_status=generation.status)
        return _response_from_generation(
            generation,
            audit_id=audit_row.audit_id,
            execution_status=audit_row.execution_status,
        )

    if body.execute and generation.candidate_sql:
        executed = execute_readonly_sql(db, question, generation.candidate_sql, current_user)
        status = "executed" if executed["execution_status"] == "executed" else "execution_failed"
        return {
            "status": status,
            "audit_id": executed["audit_id"],
            "question": question,
            "allowed": executed["allowed"],
            "sanitized_sql": executed["sanitized_sql"],
            "execution_status": executed["execution_status"],
            "row_count": executed["row_count"],
            "field_count": executed["field_count"],
            "columns": executed["columns"],
            "rows": executed["rows"],
            "execution_error": executed["execution_error"],
            "rejection_reason": generation.rejection_reason,
            "tables_used": generation.tables_used,
            "fields_used": generation.fields_used,
            "scope_injected": generation.scope_injected,
            "need_human_review": True,
            "clarification_id": None,
            "clarification_prompt": None,
            "awaiting_clarification": False,
            "turn": 1,
            "refined_question": None,
        }

    audit_row = _write_generation_audit_row(db, current_user, generation, start, execution_status="audited")
    response = _response_from_generation(
        generation,
        audit_id=audit_row.audit_id,
        execution_status=audit_row.execution_status,
    )
    if generation.status == "audit_passed":
        _store_nl2sql_cache(redis_client, current_user.tenant_id, question, generation)
        response["cache_hit"] = response.get("cache_hit", False)
    return response


def _run_clarification_follow_up(
    db: Session,
    body: Nl2SqlQueryRequest,
    current_user: MockUser,
    provider: Any,
    *,
    redis_client: RedisLike | None = None,
    merged_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    _ = redis_client, merged_context
    try:
        session = append_clarification_reply(
            db,
            current_user=current_user,
            clarification_id=body.clarification_id or "",
            reply=body.clarification_reply or "",
        )
    except (ClarificationSessionError, ClarificationAccessError) as exc:
        raise ValueError(str(exc)) from exc

    reply_texts = [item["text"] for item in session.get("replies", []) if isinstance(item, dict) and item.get("text")]
    clarification_context = build_clarification_context(
        original_question=str(session.get("original_question") or ""),
        clarification_prompt=str(session.get("clarification_prompt") or ""),
        replies=reply_texts,
    )
    refined_question = clarification_context["refined_question"]
    start = time.perf_counter()
    generation = _resolve_generation(
        refined_question,
        current_user,
        provider,
        redis_client=redis_client,
        clarification_context=clarification_context,
    )

    if generation.status == "clarification_required":
        audit_row = _write_generation_audit_row(db, current_user, generation, start, execution_status=generation.status)
        return _response_from_generation(
            generation,
            audit_id=audit_row.audit_id,
            execution_status=audit_row.execution_status,
            clarification_id=session["clarification_id"],
            clarification_prompt=generation.rejection_reason,
            awaiting_clarification=True,
            turn=session.get("turn", 1),
            refined_question=refined_question,
        )

    if generation.status != "audit_passed":
        audit_row = _write_generation_audit_row(db, current_user, generation, start, execution_status=generation.status)
        return _response_from_generation(
            generation,
            audit_id=audit_row.audit_id,
            execution_status=audit_row.execution_status,
            clarification_id=session["clarification_id"],
            clarification_prompt=session.get("clarification_prompt"),
            awaiting_clarification=False,
            turn=session.get("turn", 1),
            refined_question=refined_question,
        )

    resolve_clarification_session(
        db,
        current_user=current_user,
        clarification_id=session["clarification_id"],
        result_ref=None,
    )

    if body.execute and generation.candidate_sql:
        executed = execute_readonly_sql(db, refined_question, generation.candidate_sql, current_user)
        status = "executed" if executed["execution_status"] == "executed" else "execution_failed"
        resolve_clarification_session(
            db,
            current_user=current_user,
            clarification_id=session["clarification_id"],
            result_ref=executed["audit_id"],
        )
        return {
            "status": status,
            "audit_id": executed["audit_id"],
            "question": refined_question,
            "allowed": executed["allowed"],
            "sanitized_sql": executed["sanitized_sql"],
            "execution_status": executed["execution_status"],
            "row_count": executed["row_count"],
            "field_count": executed["field_count"],
            "columns": executed["columns"],
            "rows": executed["rows"],
            "execution_error": executed["execution_error"],
            "rejection_reason": generation.rejection_reason,
            "tables_used": generation.tables_used,
            "fields_used": generation.fields_used,
            "scope_injected": generation.scope_injected,
            "need_human_review": True,
            "clarification_id": session["clarification_id"],
            "clarification_prompt": session.get("clarification_prompt"),
            "awaiting_clarification": False,
            "turn": session.get("turn", 1),
            "refined_question": refined_question,
        }

    audit_row = _write_generation_audit_row(db, current_user, generation, start, execution_status="audited")
    resolve_clarification_session(
        db,
        current_user=current_user,
        clarification_id=session["clarification_id"],
        result_ref=audit_row.audit_id,
    )
    response = _response_from_generation(
        generation,
        audit_id=audit_row.audit_id,
        execution_status=audit_row.execution_status,
        clarification_id=session["clarification_id"],
        clarification_prompt=session.get("clarification_prompt"),
        awaiting_clarification=False,
        turn=session.get("turn", 1),
        refined_question=refined_question,
    )
    if generation.status == "audit_passed":
        _store_nl2sql_cache(redis_client, current_user.tenant_id, refined_question, generation)
    return response


def _resolve_generation(
    question: str,
    current_user: MockUser,
    provider: Any,
    *,
    redis_client: RedisLike | None = None,
    clarification_context: dict[str, Any] | None = None,
) -> CandidateGenerationResult:
    cached = read_nl2sql_cache(redis_client, current_user.tenant_id, question)
    if cached and cached.get("status") == "audit_passed":
        return CandidateGenerationResult(
            status=cached["status"],
            question=cached.get("question", question),
            candidate_sql=cached.get("candidate_sql"),
            sanitized_sql=cached.get("sanitized_sql"),
            rejection_reason=cached.get("rejection_reason"),
            tables_used=list(cached.get("tables_used") or []),
            fields_used=list(cached.get("fields_used") or []),
            scope_injected=bool(cached.get("scope_injected")),
        )
    return generate_candidate_sql(
        question,
        current_user,
        provider,
        clarification_context=clarification_context,
    )


def _store_nl2sql_cache(
    redis_client: RedisLike | None,
    tenant_id: str,
    question: str,
    generation: CandidateGenerationResult,
) -> None:
    write_nl2sql_cache(
        redis_client,
        tenant_id,
        question,
        {
            "status": generation.status,
            "question": generation.question,
            "candidate_sql": generation.candidate_sql,
            "sanitized_sql": generation.sanitized_sql,
            "rejection_reason": generation.rejection_reason,
            "tables_used": generation.tables_used,
            "fields_used": generation.fields_used,
            "scope_injected": generation.scope_injected,
        },
    )


def _validate_provider_override(body: Nl2SqlQueryRequest) -> None:
    provider_name = body.provider
    if provider_name == "mock" and settings.app_env.lower() not in LOCAL_APP_ENVS:
        raise PermissionError("mock NL2SQL provider is only allowed in local/test/development environments")
    if provider_name == "mock" and not body.mock_llm_output:
        raise ValueError("mock_llm_output is required when provider=mock")


def _write_generation_audit_row(
    db: Session,
    current_user: MockUser,
    generation: CandidateGenerationResult,
    start: float,
    execution_status: str,
) -> AgentNl2sqlAudit:
    row = AgentNl2sqlAudit(
        audit_id=f"NLSQL-{uuid.uuid4().hex[:16]}",
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        org_path=current_user.org_path,
        user_id=current_user.user_id,
        question=generation.question,
        candidate_sql=generation.candidate_sql or "",
        sanitized_sql=generation.sanitized_sql,
        allowed=generation.status == "audit_passed",
        reject_reason=generation.rejection_reason,
        tables_used=generation.tables_used,
        fields_used=generation.fields_used,
        scope_injected=generation.scope_injected,
        execution_status=execution_status,
        result_row_count=0,
        result_field_count=0,
        elapsed_ms=int((time.perf_counter() - start) * 1000),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _response_from_generation(
    generation: CandidateGenerationResult,
    audit_id: str,
    execution_status: str,
    *,
    clarification_id: str | None = None,
    clarification_prompt: str | None = None,
    awaiting_clarification: bool = False,
    turn: int = 1,
    refined_question: str | None = None,
) -> dict[str, Any]:
    return {
        "status": generation.status,
        "audit_id": audit_id,
        "question": generation.question,
        "allowed": generation.status == "audit_passed",
        "sanitized_sql": generation.sanitized_sql,
        "execution_status": execution_status,
        "row_count": 0,
        "field_count": 0,
        "columns": [],
        "rows": [],
        "execution_error": None,
        "rejection_reason": generation.rejection_reason,
        "tables_used": generation.tables_used,
        "fields_used": generation.fields_used,
        "scope_injected": generation.scope_injected,
        "need_human_review": True,
        "clarification_id": clarification_id,
        "clarification_prompt": clarification_prompt,
        "awaiting_clarification": awaiting_clarification,
        "turn": turn,
        "refined_question": refined_question,
        "cache_hit": False,
    }
