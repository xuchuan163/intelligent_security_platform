from datetime import date
from typing import Any, Literal

from pydantic import BaseModel


ProfileType = Literal["project", "worker", "subcontractor"]


class ProfileRecalculateRequest(BaseModel):
    profile_types: list[ProfileType] | None = None
    project_id: str | None = None


class ProjectProfileOut(BaseModel):
    project_id: str
    calc_date: date
    calculated_at: date
    total_risk_score: float
    risk_level: str
    data_completeness: float | None
    confidence_level: str | None
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
    calculated_at: date
    total_risk_score: float
    risk_level: str
    data_completeness: float | None
    confidence_level: str | None
    risk_tags: Any | None
    explanation: str | None
    suggestion: str | None
    worker_name_masked: str | None = None


class SubcontractorProfileOut(BaseModel):
    subcontractor_id: str
    project_id: str | None
    calc_date: date
    calculated_at: date
    total_risk_score: float
    risk_level: str
    data_completeness: float | None
    confidence_level: str | None
    high_risk_worker_ratio: float | None
    risk_tags: Any | None
    explanation: str | None
    subcontractor_name: str | None = None
