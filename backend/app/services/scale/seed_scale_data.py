"""Synthetic scale data seeding for performance tests (Phase 4-C.1)."""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    Project,
    ProjectRiskProfile,
    Subcontractor,
    SubcontractorRiskProfile,
    Tenant,
    Worker,
    WorkerRiskProfile,
)
from app.services.profiles.calculator import (
    calculate_project_profile,
    calculate_subcontractor_profile,
    calculate_worker_profile,
)

PROJECT_TYPES: tuple[str, ...] = ("housing", "municipal", "infrastructure", "mep")
CONSTRUCTION_PHASES: tuple[str, ...] = ("foundation", "main_structure", "decoration", "mep_install")
WORK_TYPES: tuple[str, ...] = ("电工", "架子工", "焊工", "普工", "塔吊司机", "信号工")
CERT_STATUSES: tuple[str, ...] = ("valid", "valid", "valid", "expired", "missing")
HEALTH_STATUSES: tuple[str, ...] = ("valid", "valid", "expired")


@dataclass(frozen=True)
class ScaleSeedConfig:
    tenant_id: str = "CSCEC-SCALE"
    tenant_name: str = "中建集团压测租户"
    project_count: int = 100
    subcontractors_per_project: int = 2
    workers_per_project: int = 8
    with_profiles: bool = True
    random_seed: int = 20260603
    batch_size: int = 200
    id_prefix: str = "SCALE"


@dataclass(frozen=True)
class ScaleSeedResult:
    tenant_id: str
    projects_created: int
    projects_updated: int
    subcontractors_created: int
    subcontractors_updated: int
    workers_created: int
    workers_updated: int
    project_profiles_upserted: int
    worker_profiles_upserted: int
    subcontractor_profiles_upserted: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "projects_created": self.projects_created,
            "projects_updated": self.projects_updated,
            "subcontractors_created": self.subcontractors_created,
            "subcontractors_updated": self.subcontractors_updated,
            "workers_created": self.workers_created,
            "workers_updated": self.workers_updated,
            "project_profiles_upserted": self.project_profiles_upserted,
            "worker_profiles_upserted": self.worker_profiles_upserted,
            "subcontractor_profiles_upserted": self.subcontractor_profiles_upserted,
            "totals": {
                "projects": self.projects_created + self.projects_updated,
                "subcontractors": self.subcontractors_created + self.subcontractors_updated,
                "workers": self.workers_created + self.workers_updated,
            },
        }


def _project_id(prefix: str, index: int) -> str:
    return f"{prefix}-P-{index:05d}"


def _subcontractor_id(prefix: str, project_index: int, slot: int) -> str:
    return f"{prefix}-S-{project_index:05d}-{slot:02d}"


def _worker_id(prefix: str, project_index: int, slot: int) -> str:
    return f"{prefix}-W-{project_index:05d}-{slot:03d}"


def _ensure_tenant(db: Session, config: ScaleSeedConfig) -> None:
    tenant = db.query(Tenant).filter(Tenant.tenant_id == config.tenant_id).first()
    if tenant is None:
        db.add(
            Tenant(
                tenant_id=config.tenant_id,
                tenant_name=config.tenant_name,
                status="active",
            )
        )
        db.flush()


def _synthetic_project_metrics(project_index: int, rng: random.Random) -> dict[str, Any]:
    return {
        "schedule_pressure_index": float(rng.randint(5, 40)),
        "night_shift_days": rng.randint(0, 7),
        "cross_operation_count": rng.randint(0, 5),
        "hazard_overdue_count": project_index % 5,
        "major_hazard_overdue_count": 1 if project_index % 17 == 0 else 0,
        "equipment_overdue_count": 1 if project_index % 23 == 0 else 0,
    }


def _upsert_project(
    db: Session,
    *,
    config: ScaleSeedConfig,
    project_index: int,
    today: dt.date,
    rng: random.Random,
) -> tuple[Project, bool]:
    project_id = _project_id(config.id_prefix, project_index)
    org_path = f"{config.tenant_id}/{config.tenant_id}-8B/REGION/{project_id}"
    metrics = _synthetic_project_metrics(project_index, rng)
    project_type = PROJECT_TYPES[project_index % len(PROJECT_TYPES)]
    payload = {
        "tenant_id": config.tenant_id,
        "company_id": config.tenant_id,
        "org_path": org_path,
        "project_name": f"压测项目-{project_index:05d}",
        "project_type": project_type,
        "construction_phase": CONSTRUCTION_PHASES[project_index % len(CONSTRUCTION_PHASES)],
        "region": "压测区",
        "status": "active",
        "start_date": today - dt.timedelta(days=365),
        "end_date": today + dt.timedelta(days=365),
        "schedule_pressure_index": metrics["schedule_pressure_index"],
        "night_shift_days": metrics["night_shift_days"],
        "cross_operation_count": metrics["cross_operation_count"],
    }

    row = db.query(Project).filter(Project.project_id == project_id).first()
    created = row is None
    if row is None:
        row = Project(project_id=project_id, **payload)
        db.add(row)
    else:
        for field, value in payload.items():
            setattr(row, field, value)
    return row, created


def _upsert_subcontractor(
    db: Session,
    *,
    config: ScaleSeedConfig,
    project: Project,
    project_index: int,
    slot: int,
    rng: random.Random,
) -> tuple[Subcontractor, bool]:
    subcontractor_id = _subcontractor_id(config.id_prefix, project_index, slot)
    org_path = f"{project.org_path}/{subcontractor_id}"
    payload = {
        "tenant_id": config.tenant_id,
        "company_id": config.tenant_id,
        "org_path": org_path,
        "subcontractor_name": f"压测分包-{project_index:05d}-{slot:02d}",
        "qualification": "一级" if slot == 1 else "二级",
        "safety_license_status": "valid" if project_index % 29 != 0 else "expired",
        "accident_history_count": 1 if project_index % 31 == 0 else 0,
        "credit_score": float(rng.randint(55, 98)),
        "status": "active",
    }

    row = db.query(Subcontractor).filter(Subcontractor.subcontractor_id == subcontractor_id).first()
    created = row is None
    if row is None:
        row = Subcontractor(subcontractor_id=subcontractor_id, **payload)
        db.add(row)
    else:
        for field, value in payload.items():
            setattr(row, field, value)
    return row, created


def _upsert_worker(
    db: Session,
    *,
    config: ScaleSeedConfig,
    project: Project,
    subcontractor: Subcontractor,
    project_index: int,
    slot: int,
    rng: random.Random,
) -> tuple[Worker, bool]:
    worker_id = _worker_id(config.id_prefix, project_index, slot)
    payload = {
        "tenant_id": config.tenant_id,
        "company_id": config.tenant_id,
        "org_path": subcontractor.org_path,
        "project_id": project.project_id,
        "subcontractor_id": subcontractor.subcontractor_id,
        "team_id": f"T-{project_index:05d}",
        "worker_name_masked": f"压测{slot:03d}**",
        "work_type": WORK_TYPES[slot % len(WORK_TYPES)],
        "age": rng.randint(22, 58),
        "special_cert_status": CERT_STATUSES[(project_index + slot) % len(CERT_STATUSES)],
        "health_check_status": HEALTH_STATUSES[(project_index + slot) % len(HEALTH_STATUSES)],
        "exam_score": float(rng.randint(45, 95)),
        "violation_count_30d": (project_index + slot) % 4,
        "violation_count_180d": (project_index + slot) % 8,
        "entry_days": rng.randint(3, 240),
        "status": "active",
    }

    row = db.query(Worker).filter(Worker.worker_id == worker_id).first()
    created = row is None
    if row is None:
        row = Worker(worker_id=worker_id, **payload)
        db.add(row)
    else:
        for field, value in payload.items():
            setattr(row, field, value)
    return row, created


def _upsert_project_profile(
    db: Session,
    *,
    project: Project,
    metrics: dict[str, Any],
    today: dt.date,
) -> None:
    profile = calculate_project_profile(
        hazard_overdue_count=metrics["hazard_overdue_count"],
        major_hazard_overdue_count=metrics["major_hazard_overdue_count"],
        equipment_overdue_count=metrics["equipment_overdue_count"],
        schedule_pressure_index=project.schedule_pressure_index,
        project_type=project.project_type,
        night_shift_days=project.night_shift_days,
        cross_operation_count=project.cross_operation_count,
    )
    row = (
        db.query(ProjectRiskProfile)
        .filter(
            ProjectRiskProfile.project_id == project.project_id,
            ProjectRiskProfile.calc_date == today,
        )
        .first()
    )
    payload = {
        "tenant_id": project.tenant_id,
        "company_id": project.company_id,
        "org_path": project.org_path,
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "confidence_level": "medium",
        "risk_tags": {"tags": profile.risk_tags},
        "strong_rule_flags": profile.evidence,
        "explanation": f"scale seed profile for {project.project_id}",
        "model_version": "scale-v1",
    }
    if row is None:
        db.add(ProjectRiskProfile(project_id=project.project_id, calc_date=today, **payload))
    else:
        for field, value in payload.items():
            setattr(row, field, value)


def _upsert_worker_profile(db: Session, *, worker: Worker, today: dt.date) -> None:
    profile = calculate_worker_profile(
        exam_score=worker.exam_score,
        violation_count_30d=worker.violation_count_30d,
        special_cert_status=worker.special_cert_status,
        health_check_status=worker.health_check_status,
        entry_days=worker.entry_days,
    )
    row = (
        db.query(WorkerRiskProfile)
        .filter(
            WorkerRiskProfile.worker_id == worker.worker_id,
            WorkerRiskProfile.calc_date == today,
        )
        .first()
    )
    payload = {
        "project_id": worker.project_id,
        "subcontractor_id": worker.subcontractor_id,
        "tenant_id": worker.tenant_id,
        "company_id": worker.company_id,
        "org_path": worker.org_path,
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "risk_tags": {"tags": profile.risk_tags},
        "explanation": f"scale seed profile for {worker.worker_id}",
        "model_version": "scale-v1",
    }
    if row is None:
        db.add(WorkerRiskProfile(worker_id=worker.worker_id, calc_date=today, **payload))
    else:
        for field, value in payload.items():
            setattr(row, field, value)


def _upsert_subcontractor_profile(
    db: Session,
    *,
    subcontractor: Subcontractor,
    project: Project,
    high_risk_worker_ratio: float,
    hazard_overdue_count: int,
    major_hazard_overdue_count: int,
    today: dt.date,
) -> None:
    profile = calculate_subcontractor_profile(
        hazard_overdue_count=hazard_overdue_count,
        major_hazard_overdue_count=major_hazard_overdue_count,
        high_risk_worker_ratio=high_risk_worker_ratio,
        safety_license_status=subcontractor.safety_license_status,
        accident_history_count=subcontractor.accident_history_count,
    )
    row = (
        db.query(SubcontractorRiskProfile)
        .filter(
            SubcontractorRiskProfile.subcontractor_id == subcontractor.subcontractor_id,
            SubcontractorRiskProfile.project_id == project.project_id,
            SubcontractorRiskProfile.calc_date == today,
        )
        .first()
    )
    payload = {
        "project_id": project.project_id,
        "tenant_id": subcontractor.tenant_id,
        "company_id": subcontractor.company_id,
        "org_path": subcontractor.org_path,
        "total_risk_score": profile.total_risk_score,
        "risk_level": profile.risk_level,
        "data_completeness": profile.data_completeness,
        "high_risk_worker_ratio": high_risk_worker_ratio,
        "risk_tags": {"tags": profile.risk_tags},
        "explanation": f"scale seed profile for {subcontractor.subcontractor_id}",
        "model_version": "scale-v1",
    }
    if row is None:
        db.add(
            SubcontractorRiskProfile(
                subcontractor_id=subcontractor.subcontractor_id,
                calc_date=today,
                **payload,
            )
        )
    else:
        for field, value in payload.items():
            setattr(row, field, value)


def seed_scale_data(db: Session, config: ScaleSeedConfig | None = None) -> ScaleSeedResult:
    config = config or ScaleSeedConfig()
    if config.project_count < 1:
        raise ValueError("project_count must be >= 1")
    if config.subcontractors_per_project < 1:
        raise ValueError("subcontractors_per_project must be >= 1")
    if config.workers_per_project < 1:
        raise ValueError("workers_per_project must be >= 1")

    rng = random.Random(config.random_seed)
    today = dt.date.today()
    _ensure_tenant(db, config)

    projects_created = projects_updated = 0
    subcontractors_created = subcontractors_updated = 0
    workers_created = workers_updated = 0
    project_profiles_upserted = worker_profiles_upserted = subcontractor_profiles_upserted = 0

    pending_writes = 0
    for project_index in range(1, config.project_count + 1):
        project, project_created = _upsert_project(
            db,
            config=config,
            project_index=project_index,
            today=today,
            rng=rng,
        )
        projects_created += int(project_created)
        projects_updated += int(not project_created)
        metrics = _synthetic_project_metrics(project_index, rng)

        project_workers: list[Worker] = []
        subcontractors: list[Subcontractor] = []
        for sub_slot in range(1, config.subcontractors_per_project + 1):
            subcontractor, sub_created = _upsert_subcontractor(
                db,
                config=config,
                project=project,
                project_index=project_index,
                slot=sub_slot,
                rng=rng,
            )
            subcontractors_created += int(sub_created)
            subcontractors_updated += int(not sub_created)
            subcontractors.append(subcontractor)

        for worker_slot in range(1, config.workers_per_project + 1):
            subcontractor = subcontractors[(worker_slot - 1) % len(subcontractors)]
            worker, worker_created = _upsert_worker(
                db,
                config=config,
                project=project,
                subcontractor=subcontractor,
                project_index=project_index,
                slot=worker_slot,
                rng=rng,
            )
            workers_created += int(worker_created)
            workers_updated += int(not worker_created)
            project_workers.append(worker)

        if config.with_profiles:
            _upsert_project_profile(db, project=project, metrics=metrics, today=today)
            project_profiles_upserted += 1

            high_risk_count = sum(
                1
                for worker in project_workers
                if worker.violation_count_30d >= 3
                or worker.special_cert_status in {"expired", "missing"}
                or (worker.exam_score is not None and worker.exam_score < 60)
            )
            high_risk_ratio = high_risk_count / max(1, len(project_workers))
            hazard_overdue = metrics["hazard_overdue_count"]
            major_hazard_overdue = metrics["major_hazard_overdue_count"]

            for worker in project_workers:
                _upsert_worker_profile(db, worker=worker, today=today)
                worker_profiles_upserted += 1

            for subcontractor in subcontractors:
                _upsert_subcontractor_profile(
                    db,
                    subcontractor=subcontractor,
                    project=project,
                    high_risk_worker_ratio=high_risk_ratio,
                    hazard_overdue_count=hazard_overdue,
                    major_hazard_overdue_count=major_hazard_overdue,
                    today=today,
                )
                subcontractor_profiles_upserted += 1

        pending_writes += 1
        if pending_writes >= config.batch_size:
            db.commit()
            pending_writes = 0

    db.commit()
    return ScaleSeedResult(
        tenant_id=config.tenant_id,
        projects_created=projects_created,
        projects_updated=projects_updated,
        subcontractors_created=subcontractors_created,
        subcontractors_updated=subcontractors_updated,
        workers_created=workers_created,
        workers_updated=workers_updated,
        project_profiles_upserted=project_profiles_upserted,
        worker_profiles_upserted=worker_profiles_upserted,
        subcontractor_profiles_upserted=subcontractor_profiles_upserted,
    )
