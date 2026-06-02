from pydantic import BaseModel
from datetime import datetime
from typing import Any


class WorkOrderCreate(BaseModel):
    work_order_type: str
    title: str
    work_order_id: str | None = None
    description: str | None = None
    project_id: str | None = None
    subcontractor_id: str | None = None
    worker_id: str | None = None
    equipment_id: str | None = None
    priority: str = "normal"
    due_time: datetime | None = None
    rule_id: str | None = None
    source_type: str | None = None
    source_id: str | None = None
    responsible_user_id: str | None = None


class WorkOrderStatusUpdate(BaseModel):
    action: str


class WorkOrderOut(BaseModel):
    work_order_id: str
    work_order_type: str
    title: str | None
    description: str | None
    project_id: str | None
    subcontractor_id: str | None
    worker_id: str | None
    status: str
    priority: str
    due_time: datetime | None
    escalation_level: int
    created_at: datetime
