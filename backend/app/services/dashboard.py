from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infrastructure.database.models import Project, ProjectRiskProfile, SafetyWorkOrder


def get_dashboard_overview(db: Session) -> dict:
    total_projects = db.scalar(select(func.count()).select_from(Project)) or 0
    high_risk_projects = (
        db.scalar(
            select(func.count())
            .select_from(ProjectRiskProfile)
            .where(ProjectRiskProfile.risk_level.in_(["high", "critical"]))
        )
        or 0
    )
    open_work_orders = (
        db.scalar(
            select(func.count())
            .select_from(SafetyWorkOrder)
            .where(SafetyWorkOrder.status.notin_(["closed", "rejected"]))
        )
        or 0
    )
    overdue_work_orders = (
        db.scalar(
            select(func.count())
            .select_from(SafetyWorkOrder)
            .where(SafetyWorkOrder.status == "overdue_escalated")
        )
        or 0
    )
    ranking_rows = db.execute(
        select(ProjectRiskProfile, Project)
        .join(Project, Project.project_id == ProjectRiskProfile.project_id)
        .order_by(ProjectRiskProfile.total_risk_score.desc())
        .limit(10)
    ).all()
    status_rows = db.execute(
        select(SafetyWorkOrder.status, func.count()).group_by(SafetyWorkOrder.status)
    ).all()

    return {
        "total_projects": total_projects,
        "high_risk_projects": high_risk_projects,
        "open_work_orders": open_work_orders,
        "overdue_work_orders": overdue_work_orders,
        "project_ranking": [
            {
                "project_id": profile.project_id,
                "project_name": project.project_name,
                "total_risk_score": profile.total_risk_score,
                "risk_level": profile.risk_level,
            }
            for profile, project in ranking_rows
        ],
        "work_order_status": [{"status": status, "count": count} for status, count in status_rows],
    }
