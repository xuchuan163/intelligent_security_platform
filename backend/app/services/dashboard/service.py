import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.infrastructure.database.models import (
    Project, ProjectRiskProfile, SafetyWorkOrder, WorkerRiskProfile,
    RuleTriggerLog, SubcontractorRiskProfile,
)


def get_dashboard_overview(db: Session) -> dict:
    today = datetime.date.today()

    total_projects = db.query(func.count(Project.id)).filter(Project.status == "active").scalar() or 0

    high_risk = db.query(func.count(ProjectRiskProfile.id)).filter(
        ProjectRiskProfile.calc_date == today,
        ProjectRiskProfile.risk_level.in_(["high", "critical"]),
    ).scalar() or 0

    critical_risk = db.query(func.count(ProjectRiskProfile.id)).filter(
        ProjectRiskProfile.calc_date == today,
        ProjectRiskProfile.risk_level == "critical",
    ).scalar() or 0

    open_orders = db.query(func.count(SafetyWorkOrder.id)).filter(
        SafetyWorkOrder.status.in_(["pending_confirm", "dispatched", "processing", "waiting_review"]),
    ).scalar() or 0

    overdue_orders = db.query(func.count(SafetyWorkOrder.id)).filter(
        SafetyWorkOrder.status == "overdue_escalated",
    ).scalar() or 0

    high_risk_workers = db.query(func.count(WorkerRiskProfile.id)).filter(
        WorkerRiskProfile.calc_date == today,
        WorkerRiskProfile.risk_level.in_(["high", "critical"]),
    ).scalar() or 0

    # Project ranking
    rankings = db.query(
        ProjectRiskProfile.project_id, ProjectRiskProfile.total_risk_score,
        ProjectRiskProfile.risk_level, Project.project_name,
    ).join(Project, Project.project_id == ProjectRiskProfile.project_id).filter(
        ProjectRiskProfile.calc_date == today,
    ).order_by(ProjectRiskProfile.total_risk_score.desc()).limit(10).all()

    project_ranking = [
        {"project_id": r.project_id, "project_name": r.project_name,
         "total_risk_score": r.total_risk_score, "risk_level": r.risk_level}
        for r in rankings
    ]

    # Recent rule triggers
    triggers = db.query(RuleTriggerLog).order_by(RuleTriggerLog.created_at.desc()).limit(20).all()
    recent_triggers = [
        {"rule_id": t.rule_id, "object_type": t.object_type, "object_id": t.object_id,
         "project_id": t.project_id, "severity": t.severity, "created_at": t.created_at.isoformat()}
        for t in triggers
    ]

    return {
        "total_projects": total_projects,
        "high_risk_projects": high_risk,
        "critical_risk_projects": critical_risk,
        "open_work_orders": open_orders,
        "overdue_work_orders": overdue_orders,
        "high_risk_workers": high_risk_workers,
        "project_ranking": project_ranking,
        "recent_rule_triggers": recent_triggers,
    }
