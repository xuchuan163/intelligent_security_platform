from pydantic import BaseModel
from typing import Any
from datetime import date


class ProjectProfileOut(BaseModel):
    project_id: str
    calc_date: date
    total_risk_score: float
    risk_level: str
    data_completeness: float | None
    risk_tags: Any | None
    explanation: str | None
    suggestion: str | None
    project_name: str | None = None
    project_type: str | None = None


class WorkerProfileOut(BaseModel):
    worker_id: str
    project_id: str | None
    subcontractor_id: str | None
    calc_date: date
    total_risk_score: float
    risk_level: str
    data_completeness: float | None
    risk_tags: Any | None
    explanation: str | None
    suggestion: str | None
    worker_name_masked: str | None = None


class SubcontractorProfileOut(BaseModel):
    subcontractor_id: str
    project_id: str | None
    calc_date: date
    total_risk_score: float
    risk_level: str
    data_completeness: float | None
    high_risk_worker_ratio: float | None
    risk_tags: Any | None
    explanation: str | None
    subcontractor_name: str | None = None
