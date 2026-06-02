import datetime
from sqlalchemy.orm import Session
from app.infrastructure.database.models import (
    ProjectRiskProfile, WorkerRiskProfile, SubcontractorRiskProfile,
    Project, Worker, Subcontractor, Hazard, Equipment,
)
from app.services.profiles.calculator import calculate_project_profile


def get_project_profile(db: Session, project_id: str) -> dict | None:
    profile = db.query(ProjectRiskProfile).filter(
        ProjectRiskProfile.project_id == project_id,
    ).order_by(ProjectRiskProfile.calc_date.desc()).first()

    if not profile:
        return None

    project = db.query(Project).filter(Project.project_id == project_id).first()
    return {
        "project_id": profile.project_id,
        "calc_date": profile.calc_date.isoformat(),
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "confidence_level": profile.confidence_level,
        "risk_tags": profile.risk_tags,
        "explanation": profile.explanation,
        "suggestion": profile.suggestion,
        "project_name": project.project_name if project else None,
        "project_type": project.project_type if project else None,
        "dimension_scores": {
            "hazard_rectification": profile.hazard_rectification_score,
            "equipment_mechanical": profile.equipment_mechanical_score,
            "schedule_pressure": profile.schedule_pressure_score,
            "subcontractor_transfer": profile.subcontractor_transfer_score,
            "behavior_risk": profile.behavior_risk_score,
        },
    }


def get_worker_profile(db: Session, worker_id: str) -> dict | None:
    profile = db.query(WorkerRiskProfile).filter(
        WorkerRiskProfile.worker_id == worker_id,
    ).order_by(WorkerRiskProfile.calc_date.desc()).first()

    if not profile:
        return None

    worker = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    return {
        "worker_id": profile.worker_id,
        "project_id": profile.project_id,
        "subcontractor_id": profile.subcontractor_id,
        "calc_date": profile.calc_date.isoformat(),
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "risk_tags": profile.risk_tags,
        "explanation": profile.explanation,
        "suggestion": profile.suggestion,
        "worker_name_masked": worker.worker_name_masked if worker else None,
        "dimension_scores": {
            "exam_risk": profile.exam_risk_score,
            "violation_risk": profile.violation_risk_score,
            "qualification_risk": profile.qualification_risk_score,
            "health_adaptation": profile.health_adaptation_score,
        },
    }


def get_subcontractor_profile(db: Session, subcontractor_id: str) -> dict | None:
    profile = db.query(SubcontractorRiskProfile).filter(
        SubcontractorRiskProfile.subcontractor_id == subcontractor_id,
    ).order_by(SubcontractorRiskProfile.calc_date.desc()).first()

    if not profile:
        return None

    sub = db.query(Subcontractor).filter(Subcontractor.subcontractor_id == subcontractor_id).first()
    return {
        "subcontractor_id": profile.subcontractor_id,
        "project_id": profile.project_id,
        "calc_date": profile.calc_date.isoformat(),
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "high_risk_worker_ratio": profile.high_risk_worker_ratio,
        "overdue_rectification_ratio": profile.overdue_rectification_ratio,
        "risk_tags": profile.risk_tags,
        "explanation": profile.explanation,
        "subcontractor_name": sub.subcontractor_name if sub else None,
        "dimension_scores": {
            "qualification_risk": profile.qualification_risk_score,
            "worker_management": profile.worker_management_score,
            "hazard_rectification": profile.hazard_rectification_score,
            "violation_risk": profile.violation_risk_score,
            "equipment_management": profile.equipment_management_score,
            "accident_credit": profile.accident_credit_score,
        },
    }


def get_project_ranking(db: Session) -> list[dict]:
    today = datetime.date.today()
    rankings = db.query(
        ProjectRiskProfile.project_id, ProjectRiskProfile.total_risk_score,
        ProjectRiskProfile.risk_level, Project.project_name,
    ).join(Project, Project.project_id == ProjectRiskProfile.project_id).filter(
        ProjectRiskProfile.calc_date == today,
    ).order_by(ProjectRiskProfile.total_risk_score.desc()).limit(20).all()

    return [
        {"project_id": r.project_id, "project_name": r.project_name,
         "total_risk_score": r.total_risk_score, "risk_level": r.risk_level}
        for r in rankings
    ]


def recalculate_project_profiles(db: Session) -> dict:
    today = datetime.date.today()
    projects = db.query(Project).filter(Project.status == "active").all()

    for project in projects:
        hazards = db.query(Hazard).filter(Hazard.project_id == project.project_id).all()
        overdue = sum(
            1
            for hazard in hazards
            if hazard.due_date and hazard.due_date < today and hazard.status != "closed"
        )
        major_overdue = sum(
            1
            for hazard in hazards
            if hazard.is_major and hazard.due_date and hazard.due_date < today and hazard.status != "closed"
        )
        equipment_overdue = db.query(Equipment).filter(
            Equipment.project_id == project.project_id,
            Equipment.use_status == "in_use",
            Equipment.inspection_due_date < today,
        ).count()

        result = calculate_project_profile(
            hazard_overdue_count=overdue,
            major_hazard_overdue_count=major_overdue,
            equipment_overdue_count=equipment_overdue,
            schedule_pressure_index=project.schedule_pressure_index,
        )

        profile = db.query(ProjectRiskProfile).filter(
            ProjectRiskProfile.project_id == project.project_id,
            ProjectRiskProfile.calc_date == today,
        ).first()
        if profile is None:
            profile = ProjectRiskProfile(
                project_id=project.project_id,
                tenant_id=project.tenant_id,
                org_path=project.org_path,
                calc_date=today,
                total_risk_score=result.total_risk_score,
                risk_level=result.risk_level,
            )
            db.add(profile)

        profile.total_risk_score = result.total_risk_score
        profile.risk_level = result.risk_level
        profile.data_completeness = result.data_completeness
        profile.confidence_level = "medium_high"
        profile.risk_tags = {"tags": result.risk_tags}
        profile.strong_rule_flags = {"evidence": result.evidence}
        profile.explanation = (
            f"项目{project.project_name}当前风险等级{result.risk_level}, "
            f"风险分{result.total_risk_score}"
        )
        profile.suggestion = "优先处理超期隐患和超期在用设备，并复核高风险作业面。"
        profile.model_version = "v1.0"

    db.commit()
    return {"recalculated_projects": len(projects)}
