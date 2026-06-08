from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import CHINA_TZ
from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import RuleTriggerLog, SafetyWorkOrder
from app.services.rules.service import RULE_NAMES
from app.services.webhooks.delivery_log import create_delivery_log, finalize_delivery_log, mask_webhook_url
from app.services.webhooks.wecom import build_wecom_markdown_payload, send_wecom_bot_message

HUMAN_REVIEW_RISK_ACTIONS = {
    "stop_work",
    "stop_and_inspect",
    "suspend_operation",
    "evict",
    "clear_out",
}


class WebhookDispatchError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def resolve_target_url(explicit: str | None = None) -> str:
    target = (explicit or "").strip() or (settings.webhook_wecom_bot_url or "").strip()
    if not target:
        raise WebhookDispatchError("Webhook URL is not configured", status_code=400)
    return target


def ensure_webhook_dispatch_allowed(*, explicit_target_url: str | None) -> None:
    if not explicit_target_url and not settings.webhook_enabled:
        raise WebhookDispatchError("Webhook delivery is disabled", status_code=403)


def _needs_human_review_for_rule(trigger: RuleTriggerLog) -> bool:
    if trigger.severity == "critical":
        return True
    return (trigger.risk_action or "") in HUMAN_REVIEW_RISK_ACTIONS


def _needs_human_review_for_work_order(order: SafetyWorkOrder) -> bool:
    return order.priority == "critical"


def _parse_trigger_row_id(trigger_id: str) -> int:
    normalized = trigger_id.strip().upper()
    if not normalized.startswith("RT-"):
        raise WebhookDispatchError("Invalid trigger_id format", status_code=422)
    try:
        return int(normalized.removeprefix("RT-"))
    except ValueError as exc:
        raise WebhookDispatchError("Invalid trigger_id format", status_code=422) from exc


def _is_order_overdue_for_webhook(order: SafetyWorkOrder, now: dt.datetime) -> bool:
    if order.status == "overdue_escalated":
        return True
    return bool(order.due_time and order.due_time < now)


def dispatch_webhook_event(
    db: Session,
    *,
    current_user: MockUser,
    event_type: str,
    event_payload: dict[str, Any],
    project_id: str | None,
    markdown_content: str,
    need_human_review: bool,
    target_url: str | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    ensure_webhook_dispatch_allowed(explicit_target_url=target_url)
    resolved_url = resolve_target_url(target_url)
    event_id = str(event_payload.get("event_id") or uuid.uuid4())

    delivery = create_delivery_log(
        db,
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        org_path=current_user.org_path,
        event_type=event_type,
        event_id=event_id,
        project_id=project_id,
        request_payload=event_payload,
        channel="wecom_bot",
        target_url=resolved_url,
        need_human_review=need_human_review,
        triggered_by=current_user.user_id,
    )

    result = send_wecom_bot_message(
        resolved_url,
        message_body=build_wecom_markdown_payload(markdown_content),
        http_client=http_client,
    )
    finalized = finalize_delivery_log(
        db,
        delivery["delivery_id"],
        delivery_status=result.delivery_status,
        response_status_code=result.response_status_code,
        response_body=result.response_body,
        error_message=result.error_message,
        elapsed_ms=result.elapsed_ms,
    )
    if finalized is None:
        raise WebhookDispatchError("Failed to finalize webhook delivery log", status_code=500)

    return {
        "delivery_id": finalized["delivery_id"],
        "delivery_status": finalized["delivery_status"],
        "event_id": event_id,
        "event_type": event_type,
        "project_id": project_id,
        "target_url_masked": mask_webhook_url(resolved_url),
        "response_status_code": finalized["response_status_code"],
        "error_message": finalized["error_message"],
        "elapsed_ms": finalized["elapsed_ms"],
        "need_human_review": need_human_review,
    }


def dispatch_rule_trigger_webhook(
    db: Session,
    *,
    trigger_id: str,
    current_user: MockUser,
    target_url: str | None = None,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    row_id = _parse_trigger_row_id(trigger_id)
    query = db.query(RuleTriggerLog).filter(RuleTriggerLog.id == row_id)
    if current_user:
        query = apply_data_scope(query, RuleTriggerLog, current_user)
    trigger = query.first()
    if trigger is None:
        raise WebhookDispatchError("Rule trigger not found", status_code=404)

    need_human_review = _needs_human_review_for_rule(trigger)
    event_id = str(uuid.uuid4())
    rule_name = RULE_NAMES.get(trigger.rule_id, trigger.rule_id)
    event_payload: dict[str, Any] = {
        "event_type": "alert.profile",
        "event_id": event_id,
        "timestamp": dt.datetime.now(CHINA_TZ).isoformat(),
        "tenant_id": current_user.tenant_id,
        "data": {
            "trigger_id": f"RT-{trigger.id:06d}",
            "rule_id": trigger.rule_id,
            "rule_name": rule_name,
            "project_id": trigger.project_id,
            "object_type": trigger.object_type,
            "object_id": trigger.object_id,
            "severity": trigger.severity,
            "evidence": trigger.evidence,
            "triggered_by": current_user.user_id,
        },
    }
    if need_human_review:
        event_payload["need_human_review"] = True

    markdown = (
        f"### 强规则预警通知\n"
        f"> 规则：`{trigger.rule_id}` {rule_name}\n"
        f"> 项目：{trigger.project_id or '-'}\n"
        f"> 对象：{trigger.object_type}/{trigger.object_id}\n"
        f"> 严重级别：{trigger.severity}\n"
        f"> 人工复核：{'是' if need_human_review else '否'}"
    )
    result = dispatch_webhook_event(
        db,
        current_user=current_user,
        event_type="alert.profile",
        event_payload=event_payload,
        project_id=trigger.project_id,
        markdown_content=markdown,
        need_human_review=need_human_review,
        target_url=target_url,
        http_client=http_client,
    )
    result["trigger_id"] = f"RT-{trigger.id:06d}"
    result["rule_id"] = trigger.rule_id
    return result


def _collect_overdue_work_orders(
    db: Session,
    *,
    current_user: MockUser,
    work_order_id: str | None,
    scan: bool,
    now: dt.datetime,
) -> list[SafetyWorkOrder]:
    query = db.query(SafetyWorkOrder)
    if current_user:
        query = apply_data_scope(query, SafetyWorkOrder, current_user)

    if work_order_id:
        order = query.filter(SafetyWorkOrder.work_order_id == work_order_id).first()
        if order is None:
            raise WebhookDispatchError("Work order not found", status_code=404)
        if not _is_order_overdue_for_webhook(order, now):
            raise WebhookDispatchError("Work order is not overdue", status_code=409)
        return [order]

    if not scan:
        raise WebhookDispatchError("work_order_id or scan=true is required", status_code=422)

    orders = query.filter(
        SafetyWorkOrder.status.in_(["processing", "waiting_review", "overdue_escalated"]),
    ).all()
    return [order for order in orders if _is_order_overdue_for_webhook(order, now)]


def dispatch_work_order_overdue_webhook(
    db: Session,
    *,
    current_user: MockUser,
    work_order_id: str | None = None,
    scan: bool = False,
    target_url: str | None = None,
    http_client: httpx.Client | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    now = now or dt.datetime.utcnow()
    orders = _collect_overdue_work_orders(
        db,
        current_user=current_user,
        work_order_id=work_order_id,
        scan=scan,
        now=now,
    )
    if not orders:
        return {"total": 0, "dispatched": [], "skipped": 0}

    dispatched: list[dict[str, Any]] = []
    for order in orders:
        need_human_review = _needs_human_review_for_work_order(order)
        event_id = str(uuid.uuid4())
        event_payload: dict[str, Any] = {
            "event_type": "work_order.overdue",
            "event_id": event_id,
            "timestamp": dt.datetime.now(CHINA_TZ).isoformat(),
            "tenant_id": current_user.tenant_id,
            "data": {
                "work_order_id": order.work_order_id,
                "project_id": order.project_id,
                "status": order.status,
                "priority": order.priority,
                "title": order.title,
                "due_time": order.due_time.isoformat() if order.due_time else None,
                "rule_id": order.rule_id,
                "triggered_by": current_user.user_id,
            },
        }
        if need_human_review:
            event_payload["need_human_review"] = True

        markdown = (
            f"### 工单超期提醒\n"
            f"> 工单：`{order.work_order_id}`\n"
            f"> 项目：{order.project_id or '-'}\n"
            f"> 标题：{order.title or '-'}\n"
            f"> 状态：{order.status} / 优先级：{order.priority}\n"
            f"> 人工复核：{'是' if need_human_review else '否'}"
        )
        dispatched.append(
            dispatch_webhook_event(
                db,
                current_user=current_user,
                event_type="work_order.overdue",
                event_payload=event_payload,
                project_id=order.project_id,
                markdown_content=markdown,
                need_human_review=need_human_review,
                target_url=target_url,
                http_client=http_client,
            )
        )

    return {
        "total": len(dispatched),
        "dispatched": dispatched,
        "work_order_ids": [order.work_order_id for order in orders],
    }
