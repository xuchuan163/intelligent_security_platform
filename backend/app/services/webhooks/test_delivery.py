from __future__ import annotations

import uuid
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.core.errors import CHINA_TZ
from app.core.security import MockUser
from app.schemas.webhooks import WebhookTestRequest
from app.services.webhooks.dispatch import (
    WebhookDispatchError,
    dispatch_webhook_event,
    ensure_webhook_dispatch_allowed,
)

# Backward-compatible alias for existing imports/tests.
WebhookTestError = WebhookDispatchError


def send_test_webhook(
    db: Session,
    *,
    request: WebhookTestRequest,
    current_user: MockUser,
    http_client: httpx.Client | None = None,
) -> dict[str, Any]:
    import datetime as dt

    ensure_webhook_dispatch_allowed(explicit_target_url=request.target_url)
    event_id = str(uuid.uuid4())
    event_payload: dict[str, Any] = {
        "event_type": request.event_type,
        "event_id": event_id,
        "timestamp": dt.datetime.now(CHINA_TZ).isoformat(),
        "tenant_id": current_user.tenant_id,
        "data": {
            "message": request.message,
            "project_id": request.project_id,
            "triggered_by": current_user.user_id,
        },
    }
    if request.need_human_review:
        event_payload["need_human_review"] = True

    project_id = request.project_id or "-"
    review_flag = "是" if request.need_human_review else "否"
    markdown = (
        f"### 中建智慧安全平台 Webhook 测试\n"
        f"> 事件：`{request.event_type}`\n"
        f"> 项目：{project_id}\n"
        f"> 人工复核：{review_flag}\n\n"
        f"{request.message}"
    )
    return dispatch_webhook_event(
        db,
        current_user=current_user,
        event_type=request.event_type,
        event_payload=event_payload,
        project_id=request.project_id,
        markdown_content=markdown,
        need_human_review=request.need_human_review,
        target_url=request.target_url,
        http_client=http_client,
    )
