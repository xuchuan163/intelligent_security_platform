import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import (
    Project,
    ProjectRiskProfile,
    RuleTriggerLog,
    SafetyWorkOrder,
    WorkerRiskProfile,
)


def get_dashboard_overview(db: Session, current_user: MockUser | None = None) -> dict:
    today = datetime.date.today()

    project_query = db.query(Project).filter(Project.status == "active")
    project_profile_query = db.query(ProjectRiskProfile)
    work_order_query = db.query(SafetyWorkOrder)
    worker_profile_query = db.query(WorkerRiskProfile)
    trigger_query = db.query(RuleTriggerLog)
    if current_user:
        project_query = apply_data_scope(project_query, Project, current_user)
        project_profile_query = apply_data_scope(project_profile_query, ProjectRiskProfile, current_user)
        work_order_query = apply_data_scope(work_order_query, SafetyWorkOrder, current_user)
        worker_profile_query = apply_data_scope(worker_profile_query, WorkerRiskProfile, current_user)
        trigger_query = apply_data_scope(trigger_query, RuleTriggerLog, current_user)

    total_projects = project_query.count()
    high_risk = project_profile_query.with_entities(func.count(ProjectRiskProfile.id)).filter(
        ProjectRiskProfile.calc_date == today,
        ProjectRiskProfile.risk_level.in_(["high", "critical"]),
    ).scalar() or 0
    critical_risk = project_profile_query.with_entities(func.count(ProjectRiskProfile.id)).filter(
        ProjectRiskProfile.calc_date == today,
        ProjectRiskProfile.risk_level == "critical",
    ).scalar() or 0
    open_orders = work_order_query.with_entities(func.count(SafetyWorkOrder.id)).filter(
        SafetyWorkOrder.status.in_(["pending_confirm", "dispatched", "processing", "waiting_review"]),
    ).scalar() or 0
    overdue_orders = work_order_query.with_entities(func.count(SafetyWorkOrder.id)).filter(
        SafetyWorkOrder.status == "overdue_escalated",
    ).scalar() or 0
    high_risk_workers = worker_profile_query.with_entities(func.count(WorkerRiskProfile.id)).filter(
        WorkerRiskProfile.calc_date == today,
        WorkerRiskProfile.risk_level.in_(["high", "critical"]),
    ).scalar() or 0

    ranking_query = db.query(
        ProjectRiskProfile.project_id,
        ProjectRiskProfile.total_risk_score,
        ProjectRiskProfile.risk_level,
        Project.project_name,
    ).join(Project, Project.project_id == ProjectRiskProfile.project_id).filter(
        ProjectRiskProfile.calc_date == today,
    )
    if current_user:
        ranking_query = apply_data_scope(ranking_query, ProjectRiskProfile, current_user)
    rankings = ranking_query.order_by(ProjectRiskProfile.total_risk_score.desc()).limit(10).all()
    project_ranking = [
        {
            "project_id": row.project_id,
            "project_name": row.project_name,
            "total_risk_score": row.total_risk_score,
            "risk_level": row.risk_level,
        }
        for row in rankings
    ]

    triggers = trigger_query.order_by(RuleTriggerLog.created_at.desc()).limit(20).all()
    recent_triggers = [
        {
            "rule_id": trigger.rule_id,
            "object_type": trigger.object_type,
            "object_id": trigger.object_id,
            "project_id": trigger.project_id,
            "severity": trigger.severity,
            "created_at": trigger.created_at.isoformat(),
        }
        for trigger in triggers
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
