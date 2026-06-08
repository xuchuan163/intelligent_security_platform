from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import MockUser
from app.infrastructure.redis_client import RedisLike
from app.services.memory.context_resolver import resolve_follow_up_context
from app.services.memory.service import append_session_memory, get_session_memory
from app.services.nl2sql.clarification import (
    append_clarification_reply,
    compose_refined_question,
    create_clarification_session,
    get_clarification_session,
)


def load_memory_context_cases(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    return [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)


def _new_category_summary() -> dict[str, int]:
    return {"total": 0, "passed": 0, "failed": 0}


def _evaluate_session_memory_case(
    db: Session,
    redis_client: RedisLike,
    current_user: MockUser,
    case: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    session_id = case["session_id"]
    turns = case["turns"]

    for turn in turns:
        append_session_memory(
            db,
            redis_client,
            current_user=current_user,
            session_id=session_id,
            message=turn["message"],
            context=turn.get("context"),
            summary=turn.get("summary"),
        )

    memory = get_session_memory(db, redis_client, current_user=current_user, session_id=session_id)
    if memory is None:
        errors.append("session memory not found after replay")
        return {"case": case, "passed": False, "errors": errors, "resolved_context": {}}

    expected_count = case.get("expected_message_count")
    if expected_count is not None and memory["message_count"] != expected_count:
        errors.append(f"message_count expected {expected_count} got {memory['message_count']}")

    last_message = turns[-1]["message"]["content"]
    resolved = resolve_follow_up_context(memory, follow_up_message=last_message)
    expected_context = case.get("expected_resolved_context") or {}
    for key, expected_value in expected_context.items():
        actual_value = resolved.get(key)
        if actual_value != expected_value:
            errors.append(f"context.{key} expected {expected_value!r} got {actual_value!r}")

    forbidden_keys = case.get("forbidden_context_keys") or []
    for key in forbidden_keys:
        if key in resolved or key in (memory.get("context") or {}):
            errors.append(f"forbidden context key present: {key}")

    expected_summary_fragment = case.get("expected_summary_fragment")
    if expected_summary_fragment and expected_summary_fragment not in (memory.get("summary") or ""):
        errors.append(f"summary missing fragment: {expected_summary_fragment}")

    return {
        "case": case,
        "passed": not errors,
        "errors": errors,
        "resolved_context": resolved,
    }


def _evaluate_clarification_case(
    db: Session,
    current_user: MockUser,
    case: dict[str, Any],
) -> dict[str, Any]:
    errors: list[str] = []
    turns = case["turns"]
    first_turn = turns[0]

    session = create_clarification_session(
        db,
        current_user=current_user,
        original_question=first_turn["original_question"],
        clarification_prompt=first_turn["clarification_prompt"],
        audit_id=first_turn.get("audit_id"),
    )
    clarification_id = session["clarification_id"]

    for turn in turns[1:]:
        if turn.get("reply"):
            append_clarification_reply(
                db,
                current_user=current_user,
                clarification_id=clarification_id,
                reply=turn["reply"],
            )

    row = get_clarification_session(db, current_user=current_user, clarification_id=clarification_id)
    if row is None:
        errors.append("clarification session not found")
        return {"case": case, "passed": False, "errors": errors, "resolved_context": {}}

    context_json = row.context_json or {}
    expected_context = case.get("expected_resolved_context") or {}
    for key, expected_value in expected_context.items():
        actual_value = context_json.get(key)
        if actual_value != expected_value:
            errors.append(f"checkpoint.{key} expected {expected_value!r} got {actual_value!r}")

    reply_texts = [
        item["text"]
        for item in context_json.get("replies", [])
        if isinstance(item, dict) and item.get("text")
    ]
    refined_question = compose_refined_question(
        original_question=str(context_json.get("original_question") or ""),
        clarification_prompt=str(context_json.get("clarification_prompt") or ""),
        replies=reply_texts,
    )
    for fragment in case.get("expected_refined_fragments") or []:
        if fragment not in refined_question:
            errors.append(f"refined_question missing fragment: {fragment}")

    expected_turn = case.get("expected_turn")
    if expected_turn is not None and context_json.get("turn") != expected_turn:
        errors.append(f"turn expected {expected_turn} got {context_json.get('turn')}")

    return {
        "case": case,
        "passed": not errors,
        "errors": errors,
        "resolved_context": context_json,
    }


def evaluate_memory_context_case(
    db: Session,
    redis_client: RedisLike,
    current_user: MockUser,
    case: dict[str, Any],
) -> dict[str, Any]:
    flow = case.get("flow", "session_memory")
    if flow == "clarification":
        return _evaluate_clarification_case(db, current_user, case)
    return _evaluate_session_memory_case(db, redis_client, current_user, case)


def run_memory_context_benchmark(
    cases: list[dict[str, Any]],
    *,
    db: Session,
    redis_client: RedisLike,
    current_user: MockUser,
) -> dict[str, Any]:
    evaluations = [
        evaluate_memory_context_case(db, redis_client, current_user, case) for case in cases
    ]
    total_cases = len(evaluations)
    passed_cases = sum(1 for item in evaluations if item["passed"])
    failures = [
        {
            "case_id": item["case"]["case_id"],
            "category": item["case"]["category"],
            "errors": item["errors"],
        }
        for item in evaluations
        if not item["passed"]
    ]

    category_summary: dict[str, dict[str, int]] = {}
    for item in evaluations:
        category = item["case"]["category"]
        summary = category_summary.setdefault(category, _new_category_summary())
        summary["total"] += 1
        if item["passed"]:
            summary["passed"] += 1
        else:
            summary["failed"] += 1

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": total_cases - passed_cases,
        "context_hit_rate": _rate(passed_cases, total_cases),
        "category_summary": category_summary,
        "failures": failures,
    }
