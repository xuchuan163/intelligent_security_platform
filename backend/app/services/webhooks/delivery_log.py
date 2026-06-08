from __future__ import annotations

import datetime as dt
import uuid
from typing import Any
from urllib.parse import parse_qsl, urlparse, urlunparse

from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import WebhookDeliveryLog

SENSITIVE_QUERY_KEYS = {"key", "token", "secret", "access_token", "signature"}
MAX_RESPONSE_BODY_LENGTH = 2000
DELIVERY_STATUSES = {"pending", "success", "failed", "skipped"}


def mask_webhook_url(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return "***"

    masked_pairs = [
        f"{key}=***" if key.lower() in SENSITIVE_QUERY_KEYS else f"{key}={value}"
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    masked_query = "&".join(masked_pairs)
    return urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, masked_query, parsed.fragment)
    )


def _truncate_text(value: str | None, *, limit: int = MAX_RESPONSE_BODY_LENGTH) -> str | None:
    if value is None:
        return None
    if len(value) <= limit:
        return value
    return value[:limit]


def _new_delivery_id() -> str:
    return f"WHDL-{uuid.uuid4().hex[:12].upper()}"


def _delivery_to_item(row: WebhookDeliveryLog) -> dict[str, Any]:
    return {
        "delivery_id": row.delivery_id,
        "tenant_id": row.tenant_id,
        "company_id": row.company_id,
        "org_path": row.org_path,
        "project_id": row.project_id,
        "event_type": row.event_type,
        "event_id": row.event_id,
        "channel": row.channel,
        "target_url_masked": row.target_url_masked,
        "request_payload": row.request_payload,
        "response_status_code": row.response_status_code,
        "response_body": row.response_body,
        "delivery_status": row.delivery_status,
        "attempt_no": row.attempt_no,
        "error_message": row.error_message,
        "need_human_review": row.need_human_review,
        "triggered_by": row.triggered_by,
        "elapsed_ms": row.elapsed_ms,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
    }


def create_delivery_log(
    db: Session,
    *,
    tenant_id: str,
    org_path: str,
    event_type: str,
    request_payload: dict[str, Any],
    channel: str = "http",
    target_url: str | None = None,
    event_id: str | None = None,
    project_id: str | None = None,
    company_id: str | None = None,
    need_human_review: bool = False,
    triggered_by: str | None = None,
    attempt_no: int = 1,
) -> dict[str, Any]:
    row = WebhookDeliveryLog(
        delivery_id=_new_delivery_id(),
        tenant_id=tenant_id,
        company_id=company_id or tenant_id,
        org_path=org_path,
        project_id=project_id,
        event_type=event_type,
        event_id=event_id,
        channel=channel,
        target_url_masked=mask_webhook_url(target_url),
        request_payload=request_payload,
        delivery_status="pending",
        attempt_no=attempt_no,
        need_human_review=need_human_review,
        triggered_by=triggered_by,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _delivery_to_item(row)


def finalize_delivery_log(
    db: Session,
    delivery_id: str,
    *,
    delivery_status: str,
    response_status_code: int | None = None,
    response_body: str | None = None,
    error_message: str | None = None,
    elapsed_ms: int | None = None,
) -> dict[str, Any] | None:
    if delivery_status not in DELIVERY_STATUSES - {"pending"}:
        raise ValueError(f"Unsupported delivery_status: {delivery_status}")

    row = db.query(WebhookDeliveryLog).filter(WebhookDeliveryLog.delivery_id == delivery_id).first()
    if row is None:
        return None

    row.delivery_status = delivery_status
    row.response_status_code = response_status_code
    row.response_body = _truncate_text(response_body)
    row.error_message = error_message
    row.elapsed_ms = elapsed_ms
    row.delivered_at = dt.datetime.utcnow()
    db.commit()
    db.refresh(row)
    return _delivery_to_item(row)


def record_webhook_delivery(
    db: Session,
    *,
    tenant_id: str,
    org_path: str,
    event_type: str,
    request_payload: dict[str, Any],
    delivery_status: str,
    channel: str = "http",
    target_url: str | None = None,
    event_id: str | None = None,
    project_id: str | None = None,
    company_id: str | None = None,
    need_human_review: bool = False,
    triggered_by: str | None = None,
    response_status_code: int | None = None,
    response_body: str | None = None,
    error_message: str | None = None,
    elapsed_ms: int | None = None,
    attempt_no: int = 1,
) -> dict[str, Any]:
    if delivery_status not in DELIVERY_STATUSES:
        raise ValueError(f"Unsupported delivery_status: {delivery_status}")

    row = WebhookDeliveryLog(
        delivery_id=_new_delivery_id(),
        tenant_id=tenant_id,
        company_id=company_id or tenant_id,
        org_path=org_path,
        project_id=project_id,
        event_type=event_type,
        event_id=event_id,
        channel=channel,
        target_url_masked=mask_webhook_url(target_url),
        request_payload=request_payload,
        response_status_code=response_status_code,
        response_body=_truncate_text(response_body),
        delivery_status=delivery_status,
        attempt_no=attempt_no,
        error_message=error_message,
        need_human_review=need_human_review,
        triggered_by=triggered_by,
        elapsed_ms=elapsed_ms,
        delivered_at=dt.datetime.utcnow() if delivery_status != "pending" else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _delivery_to_item(row)


def list_delivery_logs(
    db: Session,
    *,
    event_type: str | None = None,
    delivery_status: str | None = None,
    project_id: str | None = None,
    limit: int = 50,
    current_user: MockUser | None = None,
) -> list[dict[str, Any]]:
    query = db.query(WebhookDeliveryLog)
    if current_user:
        query = apply_data_scope(query, WebhookDeliveryLog, current_user)
    if event_type:
        query = query.filter(WebhookDeliveryLog.event_type == event_type)
    if delivery_status:
        query = query.filter(WebhookDeliveryLog.delivery_status == delivery_status)
    if project_id:
        query = query.filter(WebhookDeliveryLog.project_id == project_id)

    rows = (
        query.order_by(WebhookDeliveryLog.created_at.desc(), WebhookDeliveryLog.id.desc())
        .limit(limit)
        .all()
    )
    return [_delivery_to_item(row) for row in rows]
