from pydantic import BaseModel, Field


class WebhookTestRequest(BaseModel):
    message: str = Field(
        default="中建智慧安全平台 Webhook 沙箱测试",
        max_length=500,
    )
    event_type: str = Field(default="webhook.test", max_length=64)
    project_id: str | None = Field(default=None, max_length=64)
    target_url: str | None = Field(
        default=None,
        max_length=512,
        description="Optional sandbox bot URL; overrides WEBHOOK_WECOM_BOT_URL.",
    )
    need_human_review: bool = False


class WebhookRuleTriggerDispatchRequest(BaseModel):
    trigger_id: str = Field(..., min_length=3, max_length=32)
    target_url: str | None = Field(default=None, max_length=512)


class WebhookWorkOrderOverdueDispatchRequest(BaseModel):
    work_order_id: str | None = Field(default=None, max_length=64)
    scan: bool = Field(
        default=False,
        description="When true, dispatch webhooks for all overdue work orders in scope.",
    )
    target_url: str | None = Field(default=None, max_length=512)
