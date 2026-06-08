from __future__ import annotations

import datetime as dt

from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope
from app.infrastructure.database.models import (
    Equipment,
    Hazard,
    Project,
    ProjectRiskProfile,
    RuleTriggerLog,
    SafetyWorkOrder,
    Subcontractor,
    SubcontractorRiskProfile,
    Worker,
    WorkerRiskProfile,
)
from app.services.rules.service import RULE_NAMES

OPEN_WORK_ORDER_STATUSES = (
    "pending_confirm",
    "dispatched",
    "processing",
    "waiting_review",
)


def _week_period(week_end: dt.date) -> tuple[dt.date, dt.date, str]:
    monday = week_end - dt.timedelta(days=week_end.weekday())
    sunday = monday + dt.timedelta(days=6)
    iso_year, iso_week, _ = week_end.isocalendar()
    return monday, sunday, f"{iso_year}-W{iso_week:02d}"


def _period_datetimes(
    period_start: dt.date,
    period_end: dt.date,
) -> tuple[dt.datetime, dt.datetime]:
    start = dt.datetime.combine(period_start, dt.time.min)
    end = dt.datetime.combine(period_end, dt.time.max)
    return start, end


def _build_highlights(
    *,
    project_name: str,
    kpi: dict[str, int | float | str | None],
    rule_count: int,
    work_order_count: int,
) -> list[str]:
    highlights: list[str] = []
    risk_level = kpi.get("risk_level")
    if risk_level:
        highlights.append(
            f"{project_name}本周综合风险等级为 {risk_level}，风险分 {kpi.get('total_risk_score')}。"
        )
    if int(kpi.get("overdue_hazards") or 0) > 0:
        highlights.append(f"存在 {kpi['overdue_hazards']} 项超期未闭环隐患，需优先督办。")
    if int(kpi.get("equipment_overdue_count") or 0) > 0:
        highlights.append(
            f"有 {kpi['equipment_overdue_count']} 台在用工装设备检验超期，应停用并安排复检。"
        )
    if rule_count > 0:
        highlights.append(f"本周触发强规则 {rule_count} 次，已纳入工单与预警跟踪。")
    if int(kpi.get("open_work_orders") or 0) > 0:
        highlights.append(f"当前在途工单 {kpi['open_work_orders']} 条，其中本周相关 {work_order_count} 条。")
    if not highlights:
        highlights.append(f"{project_name}本周安全态势平稳，请继续保持巡检与交底。")
    return highlights


def get_project_weekly_report(
    db: Session,
    project_id: str,
    *,
    week_end: dt.date | None = None,
    current_user: MockUser | None = None,
) -> dict | None:
    week_end = week_end or dt.date.today()
    period_start, period_end, week_label = _week_period(week_end)
    period_start_dt, period_end_dt = _period_datetimes(period_start, period_end)

    project_query = db.query(Project).filter(
        Project.project_id == project_id,
        Project.status == "active",
    )
    if current_user:
        project_query = apply_data_scope(project_query, Project, current_user)
    project = project_query.first()
    if project is None:
        return None

    profile_query = db.query(ProjectRiskProfile).filter(
        ProjectRiskProfile.project_id == project_id,
    )
    if current_user:
        profile_query = apply_data_scope(profile_query, ProjectRiskProfile, current_user)
    profile = profile_query.order_by(ProjectRiskProfile.calc_date.desc()).first()

    hazard_query = db.query(Hazard).filter(Hazard.project_id == project_id)
    if current_user:
        hazard_query = apply_data_scope(hazard_query, Hazard, current_user)
    hazards = hazard_query.all()
    open_hazards = [h for h in hazards if h.status != "closed"]
    major_open = [h for h in open_hazards if h.is_major]
    overdue_hazards = [
        h
        for h in open_hazards
        if h.due_date is not None and h.due_date < week_end
    ]

    equipment_query = db.query(Equipment).filter(
        Equipment.project_id == project_id,
        Equipment.use_status == "in_use",
    )
    if current_user:
        equipment_query = apply_data_scope(equipment_query, Equipment, current_user)
    equipment_overdue_count = equipment_query.filter(
        Equipment.inspection_due_date.isnot(None),
        Equipment.inspection_due_date < week_end,
    ).count()

    worker_profile_query = db.query(WorkerRiskProfile).filter(
        WorkerRiskProfile.project_id == project_id,
    )
    if current_user:
        worker_profile_query = apply_data_scope(worker_profile_query, WorkerRiskProfile, current_user)
    calc_date = profile.calc_date if profile else week_end
    high_risk_workers = (
        worker_profile_query.filter(
            WorkerRiskProfile.calc_date == calc_date,
            WorkerRiskProfile.risk_level.in_(["high", "critical"]),
        ).count()
    )

    trigger_query = db.query(RuleTriggerLog).filter(
        RuleTriggerLog.project_id == project_id,
        RuleTriggerLog.created_at >= period_start_dt,
        RuleTriggerLog.created_at <= period_end_dt,
    )
    if current_user:
        trigger_query = apply_data_scope(trigger_query, RuleTriggerLog, current_user)
    triggers = trigger_query.order_by(RuleTriggerLog.created_at.desc()).limit(20).all()

    work_order_query = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.project_id == project_id)
    if current_user:
        work_order_query = apply_data_scope(work_order_query, SafetyWorkOrder, current_user)
    work_orders = (
        work_order_query.filter(
            (SafetyWorkOrder.status.in_(OPEN_WORK_ORDER_STATUSES))
            | (
                (SafetyWorkOrder.created_at >= period_start_dt)
                & (SafetyWorkOrder.created_at <= period_end_dt)
            )
        )
        .order_by(SafetyWorkOrder.priority.desc(), SafetyWorkOrder.created_at.desc())
        .limit(10)
        .all()
    )
    open_work_orders = work_order_query.filter(
        SafetyWorkOrder.status.in_(OPEN_WORK_ORDER_STATUSES),
    ).count()
    overdue_work_orders = work_order_query.filter(
        SafetyWorkOrder.status == "overdue_escalated",
    ).count()
    week_work_orders = work_order_query.filter(
        SafetyWorkOrder.created_at >= period_start_dt,
        SafetyWorkOrder.created_at <= period_end_dt,
    ).count()

    kpi = {
        "total_risk_score": profile.total_risk_score if profile else None,
        "risk_level": profile.risk_level if profile else None,
        "open_hazards": len(open_hazards),
        "major_hazards_open": len(major_open),
        "overdue_hazards": len(overdue_hazards),
        "open_work_orders": open_work_orders,
        "overdue_work_orders": overdue_work_orders,
        "week_new_work_orders": week_work_orders,
        "rule_triggers_count": len(triggers),
        "high_risk_workers": high_risk_workers,
        "equipment_overdue_count": equipment_overdue_count,
    }

    rule_triggers = [
        {
            "trigger_id": f"RT-{row.id:06d}",
            "rule_id": row.rule_id,
            "rule_name": RULE_NAMES.get(row.rule_id, row.rule_id),
            "severity": row.severity,
            "object_type": row.object_type,
            "object_id": row.object_id,
            "evidence": row.evidence,
            "created_at": row.created_at.isoformat(),
        }
        for row in triggers
    ]

    work_order_summary = [
        {
            "work_order_id": order.work_order_id,
            "work_order_type": order.work_order_type,
            "title": order.title,
            "status": order.status,
            "priority": order.priority,
            "rule_id": order.rule_id,
            "due_time": order.due_time.isoformat() if order.due_time else None,
            "created_at": order.created_at.isoformat(),
        }
        for order in work_orders
    ]

    highlights = _build_highlights(
        project_name=project.project_name,
        kpi=kpi,
        rule_count=len(triggers),
        work_order_count=len(work_orders),
    )

    return {
        "report_id": f"PWR-{project_id}-{week_label}",
        "report_type": "project_weekly",
        "tenant_id": project.tenant_id,
        "project_id": project.project_id,
        "project_name": project.project_name,
        "period": {
            "start_date": period_start.isoformat(),
            "end_date": period_end.isoformat(),
            "week_label": week_label,
        },
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "kpi": kpi,
        "rule_triggers": rule_triggers,
        "work_orders": work_order_summary,
        "highlights": highlights,
        "evidence_refs": [
            {"type": "rule_trigger", "id": item["trigger_id"], "rule_id": item["rule_id"]}
            for item in rule_triggers
        ]
        + [
            {"type": "work_order", "id": item["work_order_id"], "rule_id": item.get("rule_id")}
            for item in work_order_summary
            if item.get("rule_id")
        ],
    }


_EVAL_GRADE_BY_RISK = {
    "low": "优秀",
    "medium": "合格",
    "high": "预警",
    "critical": "不合格",
}


def _build_subcontractor_highlights(
    *,
    subcontractor_name: str,
    eval_grade: str,
    kpi: dict[str, int | float | str | None],
) -> list[str]:
    highlights: list[str] = [
        f"{subcontractor_name}当前履约评价为 {eval_grade}，综合风险分 {kpi.get('total_risk_score')}。"
    ]
    if int(kpi.get("overdue_hazards") or 0) > 0:
        highlights.append(f"有 {kpi['overdue_hazards']} 项隐患整改超期，需约谈并限期闭环。")
    if int(kpi.get("high_risk_workers") or 0) > 0:
        highlights.append(f"在场高风险工人 {kpi['high_risk_workers']} 人，建议开展专项培训与旁站。")
    if int(kpi.get("violations_30d") or 0) >= 3:
        highlights.append(f"近 30 天累计违规 {kpi['violations_30d']} 次，需强化班前交底与现场纠偏。")
    if int(kpi.get("accident_history_count") or 0) > 0:
        highlights.append(f"历史事故记录 {kpi['accident_history_count']} 起，纳入重点监管名单。")
    return highlights


def _build_subcontractor_recommendations(
    *,
    risk_level: str | None,
    kpi: dict[str, int | float | str | None],
) -> list[str]:
    recommendations: list[str] = []
    if risk_level in {"high", "critical"}:
        recommendations.append("建议总包安全员本周内组织一次分包履约约谈并留存纪要。")
    if int(kpi.get("overdue_hazards") or 0) > 0:
        recommendations.append("对超期隐患实行日清日结，重大隐患升级至项目级督办。")
    if int(kpi.get("open_work_orders") or 0) > 0:
        recommendations.append("跟踪在途整改工单闭环率，逾期自动升级 escalation。")
    if int(kpi.get("high_risk_workers") or 0) > 0:
        recommendations.append("对高风险工人执行上岗前复核，证书/体检异常人员暂停作业。")
    if not recommendations:
        recommendations.append("保持现有安全管理力度，按周复盘隐患与培训完成情况。")
    return recommendations


def get_subcontractor_eval_report(
    db: Session,
    subcontractor_id: str,
    *,
    project_id: str | None = None,
    eval_date: dt.date | None = None,
    current_user: MockUser | None = None,
) -> dict | None:
    eval_date = eval_date or dt.date.today()

    sub_query = db.query(Subcontractor).filter(
        Subcontractor.subcontractor_id == subcontractor_id,
        Subcontractor.status == "active",
    )
    if current_user:
        sub_query = apply_data_scope(sub_query, Subcontractor, current_user)
    subcontractor = sub_query.first()
    if subcontractor is None:
        return None

    profile_query = db.query(SubcontractorRiskProfile).filter(
        SubcontractorRiskProfile.subcontractor_id == subcontractor_id,
    )
    if current_user:
        profile_query = apply_data_scope(profile_query, SubcontractorRiskProfile, current_user)
    if project_id:
        profile_query = profile_query.filter(SubcontractorRiskProfile.project_id == project_id)
    profile = profile_query.order_by(SubcontractorRiskProfile.calc_date.desc()).first()

    scoped_project_id = project_id or (profile.project_id if profile else None)
    project_name: str | None = None
    if scoped_project_id:
        project_query = db.query(Project).filter(Project.project_id == scoped_project_id)
        if current_user:
            project_query = apply_data_scope(project_query, Project, current_user)
        project = project_query.first()
        project_name = project.project_name if project else None

    worker_query = db.query(Worker).filter(
        Worker.subcontractor_id == subcontractor_id,
        Worker.status == "active",
    )
    if current_user:
        worker_query = apply_data_scope(worker_query, Worker, current_user)
    if scoped_project_id:
        worker_query = worker_query.filter(Worker.project_id == scoped_project_id)
    workers = worker_query.all()
    worker_ids = [worker.worker_id for worker in workers]

    calc_date = profile.calc_date if profile else eval_date
    high_risk_workers = 0
    if worker_ids:
        worker_profile_query = db.query(WorkerRiskProfile).filter(
            WorkerRiskProfile.worker_id.in_(worker_ids),
            WorkerRiskProfile.calc_date == calc_date,
            WorkerRiskProfile.risk_level.in_(["high", "critical"]),
        )
        if current_user:
            worker_profile_query = apply_data_scope(worker_profile_query, WorkerRiskProfile, current_user)
        high_risk_workers = worker_profile_query.count()

    hazard_query = db.query(Hazard).filter(Hazard.subcontractor_id == subcontractor_id)
    if current_user:
        hazard_query = apply_data_scope(hazard_query, Hazard, current_user)
    if scoped_project_id:
        hazard_query = hazard_query.filter(Hazard.project_id == scoped_project_id)
    hazards = hazard_query.all()
    open_hazards = [hazard for hazard in hazards if hazard.status != "closed"]
    overdue_hazards = [
        hazard
        for hazard in open_hazards
        if hazard.due_date is not None and hazard.due_date < eval_date
    ]
    major_open = [hazard for hazard in open_hazards if hazard.is_major]

    work_order_query = db.query(SafetyWorkOrder).filter(
        SafetyWorkOrder.subcontractor_id == subcontractor_id,
    )
    if current_user:
        work_order_query = apply_data_scope(work_order_query, SafetyWorkOrder, current_user)
    if scoped_project_id:
        work_order_query = work_order_query.filter(SafetyWorkOrder.project_id == scoped_project_id)
    work_orders = (
        work_order_query.filter(SafetyWorkOrder.status.in_(OPEN_WORK_ORDER_STATUSES))
        .order_by(SafetyWorkOrder.priority.desc(), SafetyWorkOrder.created_at.desc())
        .limit(10)
        .all()
    )
    open_work_orders = work_order_query.filter(
        SafetyWorkOrder.status.in_(OPEN_WORK_ORDER_STATUSES),
    ).count()

    violations_30d = sum(worker.violation_count_30d for worker in workers)
    risk_level = profile.risk_level if profile else None
    eval_grade = _EVAL_GRADE_BY_RISK.get(risk_level or "", "待评估")

    kpi = {
        "total_risk_score": profile.total_risk_score if profile else None,
        "risk_level": risk_level,
        "eval_grade": eval_grade,
        "active_workers": len(workers),
        "high_risk_workers": high_risk_workers,
        "open_hazards": len(open_hazards),
        "overdue_hazards": len(overdue_hazards),
        "major_hazards_open": len(major_open),
        "open_work_orders": open_work_orders,
        "violations_30d": violations_30d,
        "accident_history_count": subcontractor.accident_history_count,
        "credit_score": subcontractor.credit_score,
        "safety_license_status": subcontractor.safety_license_status,
        "high_risk_worker_ratio": profile.high_risk_worker_ratio if profile else None,
        "overdue_rectification_ratio": profile.overdue_rectification_ratio if profile else None,
    }

    hazard_summary = [
        {
            "hazard_id": hazard.hazard_id,
            "hazard_type": hazard.hazard_type,
            "hazard_level": hazard.hazard_level,
            "status": hazard.status,
            "due_date": hazard.due_date.isoformat() if hazard.due_date else None,
            "is_major": hazard.is_major,
            "description": hazard.description,
        }
        for hazard in sorted(
            open_hazards,
            key=lambda item: (not item.is_major, item.due_date or eval_date),
        )[:5]
    ]

    work_order_summary = [
        {
            "work_order_id": order.work_order_id,
            "title": order.title,
            "status": order.status,
            "priority": order.priority,
            "rule_id": order.rule_id,
            "due_time": order.due_time.isoformat() if order.due_time else None,
        }
        for order in work_orders
    ]

    workers_summary = [
        {
            "worker_id": worker.worker_id,
            "worker_name_masked": worker.worker_name_masked,
            "work_type": worker.work_type,
            "violation_count_30d": worker.violation_count_30d,
            "special_cert_status": worker.special_cert_status,
        }
        for worker in sorted(workers, key=lambda item: item.violation_count_30d, reverse=True)[:5]
    ]

    highlights = _build_subcontractor_highlights(
        subcontractor_name=subcontractor.subcontractor_name,
        eval_grade=eval_grade,
        kpi=kpi,
    )
    recommendations = _build_subcontractor_recommendations(risk_level=risk_level, kpi=kpi)

    dimension_scores = None
    if profile:
        dimension_scores = {
            "qualification_risk": profile.qualification_risk_score,
            "worker_management": profile.worker_management_score,
            "hazard_rectification": profile.hazard_rectification_score,
            "violation_risk": profile.violation_risk_score,
            "equipment_management": profile.equipment_management_score,
            "accident_credit": profile.accident_credit_score,
        }

    return {
        "report_id": f"SER-{subcontractor_id}-{eval_date.isoformat()}",
        "report_type": "subcontractor_eval",
        "tenant_id": subcontractor.tenant_id,
        "subcontractor_id": subcontractor.subcontractor_id,
        "subcontractor_name": subcontractor.subcontractor_name,
        "project_id": scoped_project_id,
        "project_name": project_name,
        "eval_date": eval_date.isoformat(),
        "generated_at": dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),
        "profile": {
            "calc_date": profile.calc_date.isoformat() if profile else None,
            "total_risk_score": profile.total_risk_score if profile else None,
            "risk_level": risk_level,
            "eval_grade": eval_grade,
            "data_completeness": profile.data_completeness if profile else None,
            "dimension_scores": dimension_scores,
            "explanation": profile.explanation if profile else None,
        },
        "kpi": kpi,
        "hazards": hazard_summary,
        "work_orders": work_order_summary,
        "workers_summary": workers_summary,
        "highlights": highlights,
        "recommendations": recommendations,
        "evidence_refs": [
            {"type": "hazard", "id": item["hazard_id"]}
            for item in hazard_summary
        ]
        + [
            {"type": "work_order", "id": item["work_order_id"], "rule_id": item.get("rule_id")}
            for item in work_order_summary
            if item.get("rule_id")
        ],
    }
