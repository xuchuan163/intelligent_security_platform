from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AccidentCaseItem(BaseModel):
    accident_case_id: str
    tenant_id: str
    accident_type: str
    severity: str
    project_type: str | None
    operation_scene: str | None
    direct_cause: str | None
    indirect_cause: str | None
    involved_subjects: Any | None
    warning_indicators: Any | None
    rectification_measures: str | None
    tags: Any | None
    embedding_version: str | None
    status: str
    created_at: datetime
    updated_at: datetime | None = None


class AccidentCaseListOut(BaseModel):
    page_no: int
    page_size: int
    total: int
    items: list[AccidentCaseItem]
