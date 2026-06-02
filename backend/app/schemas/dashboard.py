from pydantic import BaseModel
from typing import Any


class DashboardOverview(BaseModel):
    total_projects: int
    high_risk_projects: int
    critical_risk_projects: int
    open_work_orders: int
    overdue_work_orders: int
    high_risk_workers: int
    project_ranking: list[dict[str, Any]]
    recent_rule_triggers: list[dict[str, Any]]
