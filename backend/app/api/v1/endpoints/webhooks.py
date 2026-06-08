from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints._errors import db_guard
from app.core.rbac import require_permissions
from app.core.responses import success
from app.core.security import MockUser
from app.domain.rbac import Permission
from app.infrastructure.database.session import get_db
from app.schemas.webhooks import (
    WebhookRuleTriggerDispatchRequest,
    WebhookTestRequest,
    WebhookWorkOrderOverdueDispatchRequest,
)
from app.services.webhooks.dispatch import (
    WebhookDispatchError,
    dispatch_rule_trigger_webhook,
    dispatch_work_order_overdue_webhook,
)
from app.services.webhooks.test_delivery import send_test_webhook

router = APIRouter()


@router.post("/test")
def webhook_test(
    body: WebhookTestRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    def query() -> dict:
        try:
            return send_test_webhook(db, request=body, current_user=current_user)
        except WebhookDispatchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return success(db_guard(query))


@router.post("/dispatch/rule-trigger")
def webhook_dispatch_rule_trigger(
    body: WebhookRuleTriggerDispatchRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    def query() -> dict:
        try:
            return dispatch_rule_trigger_webhook(
                db,
                trigger_id=body.trigger_id,
                current_user=current_user,
                target_url=body.target_url,
            )
        except WebhookDispatchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return success(db_guard(query))


@router.post("/dispatch/work-order-overdue")
def webhook_dispatch_work_order_overdue(
    body: WebhookWorkOrderOverdueDispatchRequest,
    db: Session = Depends(get_db),
    current_user: MockUser = Depends(require_permissions(Permission.AGENT_APPROVE)),
) -> dict:
    def query() -> dict:
        try:
            return dispatch_work_order_overdue_webhook(
                db,
                current_user=current_user,
                work_order_id=body.work_order_id,
                scan=body.scan,
                target_url=body.target_url,
            )
        except WebhookDispatchError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return success(db_guard(query))
