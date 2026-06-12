import datetime

from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.cache import invalidate_profile_cache, read_profile_cache
from app.infrastructure.redis_client import RedisLike, build_redis_client_optional
from app.infrastructure.database.models import (
    Equipment,
    Hazard,
    Project,
    ProjectRiskProfile,
    RuleTriggerLog,
    Subcontractor,
    SubcontractorRiskProfile,
    Worker,
    WorkerRiskProfile,
)
from app.schemas.profiles import ProfileRecalculateRequest
from app.services.profiles.calculator import (
    calculate_project_profile,
    calculate_subcontractor_profile,
    calculate_worker_profile,
)
from app.services.rules.work_order_trigger import (
    WorkOrderTriggerStats,
    create_work_orders_for_rule_triggers,
)

ALL_PROFILE_TYPES = ["project", "worker", "subcontractor"]


def get_project_profile(
    db: Session,
    project_id: str,
    current_user: MockUser | None = None,
    redis_client: RedisLike | None = None,
) -> dict | None:
    client = redis_client if redis_client is not None else build_redis_client_optional()

    def _load() -> dict | None:
        return _load_project_profile(db, project_id, current_user=current_user)

    return read_profile_cache(client, "project", project_id, _load)


def _load_project_profile(
    db: Session,
    project_id: str,
    current_user: MockUser | None = None,
) -> dict | None:
    query = db.query(ProjectRiskProfile)
    if current_user:
        query = apply_data_scope(query, ProjectRiskProfile, current_user)
    profile = query.filter(
        ProjectRiskProfile.project_id == project_id,
    ).order_by(ProjectRiskProfile.calc_date.desc()).first()

    if not profile:
        return None

    project_query = db.query(Project)
    if current_user:
        project_query = apply_data_scope(project_query, Project, current_user)
    project = project_query.filter(Project.project_id == project_id).first()
    return {
        "project_id": profile.project_id,
        "calc_date": profile.calc_date.isoformat(),
        "calculated_at": profile.calc_date.isoformat(),
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


def get_worker_profile(
    db: Session,
    worker_id: str,
    current_user: MockUser | None = None,
    redis_client: RedisLike | None = None,
) -> dict | None:
    client = redis_client if redis_client is not None else build_redis_client_optional()

    def _load() -> dict | None:
        return _load_worker_profile(db, worker_id, current_user=current_user)

    return read_profile_cache(client, "worker", worker_id, _load)


def _load_worker_profile(
    db: Session,
    worker_id: str,
    current_user: MockUser | None = None,
) -> dict | None:
    query = db.query(WorkerRiskProfile)
    if current_user:
        query = apply_data_scope(query, WorkerRiskProfile, current_user)
    profile = query.filter(
        WorkerRiskProfile.worker_id == worker_id,
    ).order_by(WorkerRiskProfile.calc_date.desc()).first()

    if not profile:
        return None

    worker_query = db.query(Worker)
    if current_user:
        worker_query = apply_data_scope(worker_query, Worker, current_user)
    worker = worker_query.filter(Worker.worker_id == worker_id).first()
    return {
        "worker_id": profile.worker_id,
        "project_id": profile.project_id,
        "subcontractor_id": profile.subcontractor_id,
        "calc_date": profile.calc_date.isoformat(),
        "calculated_at": profile.calc_date.isoformat(),
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "confidence_level": profile.confidence_level,
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


def get_subcontractor_profile(
    db: Session,
    subcontractor_id: str,
    current_user: MockUser | None = None,
    redis_client: RedisLike | None = None,
) -> dict | None:
    client = redis_client if redis_client is not None else build_redis_client_optional()

    def _load() -> dict | None:
        return _load_subcontractor_profile(db, subcontractor_id, current_user=current_user)

    return read_profile_cache(client, "subcontractor", subcontractor_id, _load)


def _load_subcontractor_profile(
    db: Session,
    subcontractor_id: str,
    current_user: MockUser | None = None,
) -> dict | None:
    query = db.query(SubcontractorRiskProfile)
    if current_user:
        query = apply_data_scope(query, SubcontractorRiskProfile, current_user)
    profile = query.filter(
        SubcontractorRiskProfile.subcontractor_id == subcontractor_id,
    ).order_by(SubcontractorRiskProfile.calc_date.desc()).first()

    if not profile:
        return None

    sub_query = db.query(Subcontractor)
    if current_user:
        sub_query = apply_data_scope(sub_query, Subcontractor, current_user)
    sub = sub_query.filter(Subcontractor.subcontractor_id == subcontractor_id).first()
    return {
        "subcontractor_id": profile.subcontractor_id,
        "project_id": profile.project_id,
        "calc_date": profile.calc_date.isoformat(),
        "calculated_at": profile.calc_date.isoformat(),
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "confidence_level": profile.confidence_level,
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


def list_workers(
    db: Session,
    *,
    project_id: str | None = None,
    limit: int = 200,
    current_user: MockUser | None = None,
) -> list[dict]:
    today = datetime.date.today()
    query = db.query(Worker).filter(Worker.status == "active")
    if current_user:
        query = apply_data_scope(query, Worker, current_user)
    if project_id:
        query = query.filter(Worker.project_id == project_id)

    workers = query.order_by(Worker.project_id, Worker.worker_id).limit(limit).all()
    if not workers:
        return []

    worker_ids = [worker.worker_id for worker in workers]
    profile_rows = (
        db.query(WorkerRiskProfile)
        .filter(
            WorkerRiskProfile.worker_id.in_(worker_ids),
            WorkerRiskProfile.calc_date == today,
        )
        .all()
    )
    profile_by_worker = {row.worker_id: row for row in profile_rows}

    items: list[dict] = []
    for worker in workers:
        profile = profile_by_worker.get(worker.worker_id)
        items.append(
            {
                "worker_id": worker.worker_id,
                "worker_name_masked": worker.worker_name_masked,
                "work_type": worker.work_type,
                "project_id": worker.project_id,
                "subcontractor_id": worker.subcontractor_id,
                "special_cert_status": worker.special_cert_status,
                "violation_count_30d": worker.violation_count_30d,
                "risk_level": profile.risk_level if profile else None,
                "total_risk_score": profile.total_risk_score if profile else None,
            }
        )
    return items


def get_project_ranking(db: Session, current_user: MockUser | None = None) -> list[dict]:
    today = datetime.date.today()
    query = db.query(
        ProjectRiskProfile.project_id,
        ProjectRiskProfile.total_risk_score,
        ProjectRiskProfile.risk_level,
        Project.project_name,
    ).join(Project, Project.project_id == ProjectRiskProfile.project_id).filter(
        ProjectRiskProfile.calc_date == today,
    )
    if current_user:
        query = apply_data_scope(query, ProjectRiskProfile, current_user)
    rankings = query.order_by(ProjectRiskProfile.total_risk_score.desc()).limit(20).all()

    return [
        {
            "project_id": r.project_id,
            "project_name": r.project_name,
            "total_risk_score": r.total_risk_score,
            "risk_level": r.risk_level,
        }
        for r in rankings
    ]


def recalculate_profiles(
    db: Session,
    request: ProfileRecalculateRequest | None = None,
    current_user: MockUser | None = None,
) -> dict:
    request = request or ProfileRecalculateRequest()
    profile_types = request.profile_types or ALL_PROFILE_TYPES
    result = {
        "recalculated_projects": 0,
        "recalculated_workers": 0,
        "recalculated_subcontractors": 0,
        "created_work_orders": 0,
        "skipped_duplicate_work_orders": 0,
    }

    if "project" in profile_types:
        _merge_counts(result, recalculate_project_profiles(db, current_user=current_user, project_id=request.project_id))
    if "worker" in profile_types:
        _merge_counts(result, recalculate_worker_profiles(db, current_user=current_user, project_id=request.project_id))
    if "subcontractor" in profile_types:
        _merge_counts(result, recalculate_subcontractor_profiles(db, current_user=current_user, project_id=request.project_id))

    return result


def recalculate_project_profiles(
    db: Session,
    current_user: MockUser | None = None,
    project_id: str | None = None,
) -> dict:
    today = datetime.date.today()
    query = db.query(Project).filter(Project.status == "active")
    if current_user:
        query = apply_data_scope(query, Project, current_user)
    if project_id:
        query = query.filter(Project.project_id == project_id)
    projects = query.all()
    work_order_stats = WorkOrderTriggerStats()

    redis_client = build_redis_client_optional()
    for project in projects:
        hazards = db.query(Hazard).filter(Hazard.project_id == project.project_id).all()
        overdue = sum(1 for hazard in hazards if _is_overdue_open_hazard(hazard, today))
        major_overdue = sum(1 for hazard in hazards if hazard.is_major and _is_overdue_open_hazard(hazard, today))
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
            project_type=project.project_type,
            night_shift_days=project.night_shift_days,
            cross_operation_count=project.cross_operation_count,
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
        profile.explanation = f"Project {project.project_name} risk level is {result.risk_level}."
        profile.suggestion = "Prioritize overdue hazards and overdue in-use equipment."
        profile.model_version = "v1.0"

        for trigger in result.rule_triggers:
            db.add(_rule_trigger_log(trigger, project, "project", project.project_id, project.project_id))
        work_order_stats.add(
            create_work_orders_for_rule_triggers(
                db,
                result.rule_triggers,
                project,
                "project",
                project.project_id,
                project.project_id,
            )
        )
        invalidate_profile_cache(redis_client, "project", project.project_id)

    db.commit()
    return {"recalculated_projects": len(projects), **work_order_stats.to_dict()}


def recalculate_worker_profiles(
    db: Session,
    current_user: MockUser | None = None,
    project_id: str | None = None,
) -> dict:
    today = datetime.date.today()
    query = db.query(Worker).filter(Worker.status == "active")
    if current_user:
        query = apply_data_scope(query, Worker, current_user)
    if project_id:
        query = query.filter(Worker.project_id == project_id)
    workers = query.all()
    work_order_stats = WorkOrderTriggerStats()
    redis_client = build_redis_client_optional()

    for worker in workers:
        result = calculate_worker_profile(
            exam_score=worker.exam_score,
            violation_count_30d=worker.violation_count_30d,
            special_cert_status=worker.special_cert_status,
            health_check_status=worker.health_check_status,
            entry_days=worker.entry_days,
        )
        profile = db.query(WorkerRiskProfile).filter(
            WorkerRiskProfile.worker_id == worker.worker_id,
            WorkerRiskProfile.project_id == worker.project_id,
            WorkerRiskProfile.calc_date == today,
        ).first()
        if profile is None:
            profile = WorkerRiskProfile(
                worker_id=worker.worker_id,
                project_id=worker.project_id,
                subcontractor_id=worker.subcontractor_id,
                tenant_id=worker.tenant_id,
                org_path=worker.org_path,
                calc_date=today,
                total_risk_score=result.total_risk_score,
                risk_level=result.risk_level,
            )
            db.add(profile)

        profile.subcontractor_id = worker.subcontractor_id
        profile.total_risk_score = result.total_risk_score
        profile.risk_level = result.risk_level
        profile.data_completeness = result.data_completeness
        profile.confidence_level = "medium"
        profile.exam_risk_score = _exam_risk_score(worker.exam_score)
        profile.violation_risk_score = min(100, worker.violation_count_30d * 20)
        profile.qualification_risk_score = 100 if worker.special_cert_status in ("expired", "missing") else 0
        profile.health_adaptation_score = 60 if worker.health_check_status == "expired" else 0
        profile.operation_context_score = 30 if worker.entry_days < 7 else 0
        profile.risk_tags = {"tags": result.risk_tags}
        profile.strong_rule_flags = {"evidence": result.evidence}
        profile.explanation = f"Worker {worker.worker_id} risk level is {result.risk_level}."
        profile.suggestion = "Review certificates, training records, and recent violations."
        profile.model_version = "v1.0"

        for trigger in result.rule_triggers:
            db.add(_rule_trigger_log(trigger, worker, "worker", worker.worker_id, worker.project_id))
        work_order_stats.add(
            create_work_orders_for_rule_triggers(
                db,
                result.rule_triggers,
                worker,
                "worker",
                worker.worker_id,
                worker.project_id,
            )
        )
        invalidate_profile_cache(redis_client, "worker", worker.worker_id)

    db.commit()
    return {"recalculated_workers": len(workers), **work_order_stats.to_dict()}


def recalculate_subcontractor_profiles(
    db: Session,
    current_user: MockUser | None = None,
    project_id: str | None = None,
) -> dict:
    today = datetime.date.today()
    query = db.query(Subcontractor).filter(Subcontractor.status == "active")
    if current_user:
        query = apply_data_scope(query, Subcontractor, current_user)
    if project_id:
        scoped_ids = _subcontractor_ids_for_project(db, project_id)
        query = query.filter(Subcontractor.subcontractor_id.in_(scoped_ids or ["__none__"]))
    subcontractors = query.all()
    work_order_stats = WorkOrderTriggerStats()
    redis_client = build_redis_client_optional()

    for sub in subcontractors:
        hazard_query = db.query(Hazard).filter(Hazard.subcontractor_id == sub.subcontractor_id)
        worker_query = db.query(Worker).filter(Worker.subcontractor_id == sub.subcontractor_id, Worker.status == "active")
        if project_id:
            hazard_query = hazard_query.filter(Hazard.project_id == project_id)
            worker_query = worker_query.filter(Worker.project_id == project_id)

        hazards = hazard_query.all()
        workers = worker_query.all()
        overdue = sum(1 for hazard in hazards if _is_overdue_open_hazard(hazard, today))
        major_overdue = sum(1 for hazard in hazards if hazard.is_major and _is_overdue_open_hazard(hazard, today))
        high_risk_workers = _high_risk_worker_count(db, today, workers)
        high_risk_ratio = round(high_risk_workers / len(workers), 4) if workers else 0.0

        result = calculate_subcontractor_profile(
            hazard_overdue_count=overdue,
            major_hazard_overdue_count=major_overdue,
            high_risk_worker_ratio=high_risk_ratio,
            safety_license_status=sub.safety_license_status,
            accident_history_count=sub.accident_history_count,
        )

        profile = db.query(SubcontractorRiskProfile).filter(
            SubcontractorRiskProfile.subcontractor_id == sub.subcontractor_id,
            SubcontractorRiskProfile.project_id == project_id,
            SubcontractorRiskProfile.calc_date == today,
        ).first()
        if profile is None:
            profile = SubcontractorRiskProfile(
                subcontractor_id=sub.subcontractor_id,
                project_id=project_id,
                tenant_id=sub.tenant_id,
                org_path=sub.org_path,
                calc_date=today,
                total_risk_score=result.total_risk_score,
                risk_level=result.risk_level,
            )
            db.add(profile)

        profile.total_risk_score = result.total_risk_score
        profile.risk_level = result.risk_level
        profile.data_completeness = result.data_completeness
        profile.confidence_level = "medium"
        profile.qualification_risk_score = 100 if sub.safety_license_status == "expired" else 0
        profile.worker_management_score = high_risk_ratio * 100
        profile.hazard_rectification_score = min(100, overdue * 20)
        profile.violation_risk_score = min(100, sum(worker.violation_count_30d for worker in workers) * 10)
        profile.accident_credit_score = min(100, sub.accident_history_count * 30)
        profile.high_risk_worker_ratio = high_risk_ratio
        profile.overdue_rectification_ratio = round(overdue / len(hazards), 4) if hazards else 0.0
        profile.risk_tags = {"tags": result.risk_tags}
        profile.strong_rule_flags = {"evidence": result.evidence}
        profile.explanation = f"Subcontractor {sub.subcontractor_id} risk level is {result.risk_level}."
        profile.suggestion = "Review license status, overdue hazards, and high-risk worker management."
        profile.model_version = "v1.0"

        for trigger in result.rule_triggers:
            db.add(_rule_trigger_log(trigger, sub, "subcontractor", sub.subcontractor_id, project_id))
        work_order_stats.add(
            create_work_orders_for_rule_triggers(
                db,
                result.rule_triggers,
                sub,
                "subcontractor",
                sub.subcontractor_id,
                project_id,
            )
        )
        invalidate_profile_cache(redis_client, "subcontractor", sub.subcontractor_id)

    db.commit()
    return {
        "recalculated_subcontractors": len(subcontractors),
        **work_order_stats.to_dict(),
    }


def _merge_counts(target: dict, patch: dict) -> None:
    for key, value in patch.items():
        target[key] = target.get(key, 0) + value


def _is_overdue_open_hazard(hazard: Hazard, today: datetime.date) -> bool:
    return bool(hazard.due_date and hazard.due_date < today and hazard.status != "closed")


def _rule_trigger_log(trigger: dict, source, object_type: str, object_id: str, project_id: str | None) -> RuleTriggerLog:
    return RuleTriggerLog(
        rule_id=trigger["rule_id"],
        tenant_id=source.tenant_id,
        org_path=source.org_path,
        object_type=object_type,
        object_id=object_id,
        project_id=project_id,
        trigger_condition=str(trigger["evidence"]),
        evidence=trigger,
        risk_action=trigger.get("suggested_work_order_type"),
        severity=trigger["severity"],
    )


def _exam_risk_score(exam_score: float | None) -> float | None:
    if exam_score is None:
        return None
    return max(0, 60 - exam_score)


def _subcontractor_ids_for_project(db: Session, project_id: str) -> list[str]:
    worker_ids = db.query(Worker.subcontractor_id).filter(
        Worker.project_id == project_id,
        Worker.subcontractor_id.isnot(None),
    )
    hazard_ids = db.query(Hazard.subcontractor_id).filter(
        Hazard.project_id == project_id,
        Hazard.subcontractor_id.isnot(None),
    )
    return sorted({row[0] for row in worker_ids.union(hazard_ids).all()})


def _high_risk_worker_count(db: Session, today: datetime.date, workers: list[Worker]) -> int:
    if not workers:
        return 0
    worker_ids = [worker.worker_id for worker in workers]
    return db.query(WorkerRiskProfile).filter(
        WorkerRiskProfile.calc_date == today,
        WorkerRiskProfile.worker_id.in_(worker_ids),
        WorkerRiskProfile.risk_level.in_(["high", "critical"]),
    ).count()
