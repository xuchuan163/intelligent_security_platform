from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import AgentApprovalRequest
from app.schemas.work_orders import WorkOrderCreate, WorkOrderStatusUpdate
from app.services.work_orders.service import create_work_order
from app.services.work_orders.workflow import transition_work_order


ApprovalDecision = Literal["approved", "rejected"]

_PAYLOAD_KEYS = {
    "project_id",
    "work_order_id",
    "hazard_id",
    "action",
    "assignee_user_id",
    "due_time",
    "reject_reason",
    "comment",
    "title",
    "description",
    "work_order_type",
    "source_type",
    "source_id",
    "priority",
    "rule_id",
    "propose_work_order",
}


def create_approval_request_for_step(
    db: Session,
    *,
    run_id: str,
    step_run_id: str,
    step: dict[str, Any],
    tool_name: str,
    context: dict[str, Any],
    current_user: MockUser,
    reason: str | None,
) -> AgentApprovalRequest:
    target_type, target_id = _target_from_context(tool_name, context)
    approval = AgentApprovalRequest(
        approval_id=f"AGAPR-{uuid.uuid4().hex[:16]}",
        run_id=run_id,
        step_run_id=step_run_id,
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        project_id=context.get("project_id"),
        scope_type=current_user.scope_type.value if current_user.scope_type else "company",
        request_user_id=current_user.user_id,
        requested_tool=tool_name,
        requested_action=step.get("action") or "unknown",
        target_type=target_type,
        target_id=target_id,
        payload_summary=_payload_summary(tool_name, step, target_id),
        payload_json=_sanitized_payload(context),
        risk_level=_risk_level(tool_name),
        reason=reason,
        evidence_refs=context.get("evidence_refs") if isinstance(context.get("evidence_refs"), list) else [],
        status="pending",
        created_at=_now(),
        updated_at=_now(),
    )
    db.add(approval)
    db.flush()
    return approval


def list_approval_requests(
    db: Session,
    *,
    current_user: MockUser,
    status: str | None = "pending",
    limit: int = 50,
) -> dict[str, Any]:
    query = apply_data_scope(db.query(AgentApprovalRequest), AgentApprovalRequest, current_user)
    if status:
        query = query.filter(AgentApprovalRequest.status == status)
    rows = query.order_by(AgentApprovalRequest.created_at.desc(), AgentApprovalRequest.id.desc()).limit(limit).all()
    return {"items": [_approval_to_dict(row) for row in rows], "total": len(rows)}


def get_approval_request(
    db: Session,
    *,
    approval_id: str,
    current_user: MockUser,
) -> AgentApprovalRequest | None:
    return apply_data_scope(
        db.query(AgentApprovalRequest).filter(AgentApprovalRequest.approval_id == approval_id),
        AgentApprovalRequest,
        current_user,
    ).first()


def decide_approval_request(
    db: Session,
    *,
    approval_id: str,
    current_user: MockUser,
    decision: ApprovalDecision,
    comment: str | None = None,
) -> dict[str, Any] | None:
    approval = get_approval_request(db, approval_id=approval_id, current_user=current_user)
    if approval is None:
        return None
    if approval.status != "pending":
        raise ValueError("Only pending approval requests can be decided")

    now = _now()
    approval.status = decision
    approval.approver_user_id = current_user.user_id
    approval.approval_comment = comment
    approval.updated_at = now
    if decision == "approved":
        approval.approved_at = now
    else:
        approval.rejected_at = now
    db.commit()
    db.refresh(approval)
    return _approval_to_dict(approval)


def execute_approved_request(
    db: Session,
    *,
    approval_id: str,
    current_user: MockUser,
) -> dict[str, Any] | None:
    approval = get_approval_request(db, approval_id=approval_id, current_user=current_user)
    if approval is None:
        return None
    if approval.status != "approved":
        raise ValueError("Only approved approval requests can be executed")

    try:
        _assert_executable_tool(approval)
        if approval.requested_tool == "work_orders.create":
            result = _execute_work_order_create(db, approval, current_user)
        else:
            result = _execute_work_order_transition(db, approval, current_user)
    except Exception as exc:
        db.rollback()
        _mark_execution_failed(
            db,
            approval_id=approval_id,
            current_user=current_user,
            error_message=str(exc),
        )
        raise

    stored = get_approval_request(db, approval_id=approval_id, current_user=current_user)
    if stored is None:
        return None
    stored.status = "executed"
    stored.executor_user_id = current_user.user_id
    stored.executed_at = _now()
    stored.execution_result = result
    stored.execution_error = None
    stored.updated_at = _now()
    db.commit()
    db.refresh(stored)
    return _approval_to_dict(stored)


def approval_to_dict(approval: AgentApprovalRequest) -> dict[str, Any]:
    return _approval_to_dict(approval)


def _assert_executable_tool(approval: AgentApprovalRequest) -> None:
    if approval.requested_tool not in {"work_orders.transition", "work_orders.create"}:
        raise PermissionError("Only approved work order tools can be executed in controlled Agent mode")
    if approval.requested_tool == "work_orders.transition" and approval.target_type != "work_order":
        raise PermissionError("work_orders.transition approvals must target a work order")
    if approval.requested_tool == "work_orders.create" and approval.target_type not in {"hazard", "unknown"}:
        raise PermissionError("work_orders.create approvals must target a hazard context")


def _execute_work_order_create(
    db: Session,
    approval: AgentApprovalRequest,
    current_user: MockUser,
) -> dict[str, Any]:
    payload_json = approval.payload_json or {}
    if not isinstance(payload_json, dict):
        raise ValueError("Approval payload must be an object")

    project_id = payload_json.get("project_id") or approval.project_id
    hazard_id = payload_json.get("hazard_id") or approval.target_id
    if not project_id:
        raise ValueError("project_id is required")
    if not hazard_id:
        raise ValueError("hazard_id is required")

    data = WorkOrderCreate(
        work_order_type=payload_json.get("work_order_type") or "hazard_rectification",
        title=payload_json.get("title") or "Agent suggested hazard rectification",
        description=payload_json.get("description"),
        project_id=project_id,
        source_type=payload_json.get("source_type") or "hazard",
        source_id=payload_json.get("source_id") or hazard_id,
        priority=payload_json.get("priority") or "normal",
        rule_id=payload_json.get("rule_id"),
    )
    order = create_work_order(db, data, current_user)
    return {
        "work_order_id": order.work_order_id,
        "status": order.status,
        "project_id": order.project_id,
        "source_type": order.source_type,
        "source_id": order.source_id,
    }


def _execute_work_order_transition(
    db: Session,
    approval: AgentApprovalRequest,
    current_user: MockUser,
) -> dict[str, Any]:
    payload_json = approval.payload_json or {}
    if not isinstance(payload_json, dict):
        raise ValueError("Approval payload must be an object")
    work_order_id = payload_json.get("work_order_id") or approval.target_id
    if not work_order_id:
        raise ValueError("work_order_id is required")

    payload = WorkOrderStatusUpdate(
        action=payload_json.get("action"),
        comment=payload_json.get("comment"),
        assignee_user_id=payload_json.get("assignee_user_id"),
        due_time=payload_json.get("due_time"),
        reject_reason=payload_json.get("reject_reason"),
        attachments=payload_json.get("attachments"),
    )
    result = transition_work_order(db, work_order_id, payload, current_user)
    if result is None:
        raise ValueError("Work order not found")
    return result


def _mark_execution_failed(
    db: Session,
    *,
    approval_id: str,
    current_user: MockUser,
    error_message: str,
) -> None:
    approval = get_approval_request(db, approval_id=approval_id, current_user=current_user)
    if approval is None:
        return
    approval.status = "execution_failed"
    approval.executor_user_id = current_user.user_id
    approval.execution_error = error_message
    approval.updated_at = _now()
    db.commit()


def _target_from_context(tool_name: str, context: dict[str, Any]) -> tuple[str, str | None]:
    if tool_name == "work_orders.create":
        hazard_id = context.get("hazard_id")
        if hazard_id is None and context.get("source_type") == "hazard":
            hazard_id = context.get("source_id")
        if hazard_id:
            return "hazard", hazard_id
    if tool_name.startswith("work_orders."):
        return "work_order", context.get("work_order_id")
    if tool_name.startswith("hazards."):
        return "hazard", context.get("hazard_id")
    return "unknown", None


def _sanitized_payload(context: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in context.items() if key in _PAYLOAD_KEYS}


def _payload_summary(tool_name: str, step: dict[str, Any], target_id: str | None) -> str:
    target = target_id or "unresolved target"
    action = step.get("action") or "unknown action"
    return f"{tool_name} requests {action} for {target}"


def _risk_level(tool_name: str) -> str:
    if tool_name in {"work_orders.transition", "work_orders.dispatch", "work_orders.create"}:
        return "medium"
    return "high"


def _approval_to_dict(approval: AgentApprovalRequest) -> dict[str, Any]:
    return {
        "approval_id": approval.approval_id,
        "run_id": approval.run_id,
        "step_run_id": approval.step_run_id,
        "company_id": approval.company_id,
        "project_id": approval.project_id,
        "scope_type": approval.scope_type,
        "request_user_id": approval.request_user_id,
        "requested_tool": approval.requested_tool,
        "requested_action": approval.requested_action,
        "target_type": approval.target_type,
        "target_id": approval.target_id,
        "payload_summary": approval.payload_summary,
        "payload_json": approval.payload_json,
        "risk_level": approval.risk_level,
        "reason": approval.reason,
        "evidence_refs": approval.evidence_refs,
        "status": approval.status,
        "approver_user_id": approval.approver_user_id,
        "approval_comment": approval.approval_comment,
        "executor_user_id": approval.executor_user_id,
        "executed_at": _date_to_string(approval.executed_at),
        "execution_result": approval.execution_result,
        "execution_error": approval.execution_error,
        "created_at": _date_to_string(approval.created_at),
        "updated_at": _date_to_string(approval.updated_at),
        "approved_at": _date_to_string(approval.approved_at),
        "rejected_at": _date_to_string(approval.rejected_at),
        "expires_at": _date_to_string(approval.expires_at),
    }


def _date_to_string(value: Any) -> str | None:
    return value.isoformat() if value else None


def _now() -> dt.datetime:
    return dt.datetime.utcnow()
