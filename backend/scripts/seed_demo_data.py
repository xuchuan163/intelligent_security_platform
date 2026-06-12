"""Seed demo data for the CSCEC Smart Safety Platform MVP."""

import datetime
import random
import sys
from pathlib import Path
from typing import Any

import yaml

# Allow this script to run directly from PyCharm/main.py while still importing
# the backend package as ``app``.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy.orm import Session
from app.infrastructure.database.session import SessionLocal, engine, Base
from app.infrastructure.database.models import (
    Tenant, Project, Subcontractor, Worker, Hazard, Equipment,
    ProjectRiskProfile, WorkerRiskProfile, SubcontractorRiskProfile,
    RuleTriggerLog, SafetyWorkOrder, MetricCatalog,
    ProjectUser, WorkOrderFlowLog,
)
from app.services.profiles.calculator import (
    calculate_project_profile, calculate_worker_profile, calculate_subcontractor_profile,
)
from app.services.agents.prompt_registry import sync_agent_prompt_versions
from app.services.auth.seed_rbac import seed_rbac_foundation
from app.services.cases.seed_cases import seed_accident_cases
from app.services.seed.mock_enrichment import seed_mock_enrichment

ROOT_DIR = BACKEND_ROOT.parent
METRIC_CATALOG_PATH = ROOT_DIR / "config" / "metrics" / "catalog.yaml"


def seed_metrics(db: Session) -> None:
    payload = yaml.safe_load(METRIC_CATALOG_PATH.read_text(encoding="utf-8")) or {}
    metrics: list[dict[str, Any]] = payload.get("metrics", [])

    for metric in metrics:
        row = db.query(MetricCatalog).filter(MetricCatalog.metric_code == metric["metric_code"]).first()
        if row is None:
            row = MetricCatalog(metric_code=metric["metric_code"], metric_name=metric["metric_name"], business_definition=metric["business_definition"])
            db.add(row)
        for field, value in metric.items():
            setattr(row, field, value)
    db.commit()


def seed_work_order_workflow_demo(db: Session) -> None:
    """Seed P002 role accounts and a deterministic hazard workflow demo order."""

    today = datetime.date.today()
    project = db.query(Project).filter(Project.project_id == "P002").first()
    if project is None:
        project = Project(
            project_id="P002",
            tenant_id="CSCEC",
            company_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P002",
            project_name="武汉长江中心",
            project_type="housing",
            construction_phase="foundation",
            region="华中",
            status="active",
            start_date=today - datetime.timedelta(days=365),
            end_date=today + datetime.timedelta(days=365),
        )
        db.add(project)
        db.flush()

    roles = [
        {
            "user_id": "U-GC-01",
            "user_name": "李安全",
            "role_code": "gc_safety_officer",
            "subcontractor_id": None,
        },
        {
            "user_id": "U-DIR-01",
            "user_name": "王总监",
            "role_code": "safety_director",
            "subcontractor_id": None,
        },
        {
            "user_id": "U-SUB-S003",
            "user_name": "陈分包",
            "role_code": "sub_safety_officer",
            "subcontractor_id": "S003",
        },
    ]
    for payload in roles:
        role = (
            db.query(ProjectUser)
            .filter(
                ProjectUser.project_id == "P002",
                ProjectUser.user_id == payload["user_id"],
                ProjectUser.role_code == payload["role_code"],
            )
            .first()
        )
        if role is None:
            role = ProjectUser(
                tenant_id=project.tenant_id,
                company_id=project.company_id,
                org_path=project.org_path,
                project_id="P002",
                user_id=payload["user_id"],
                role_code=payload["role_code"],
                user_name=payload["user_name"],
            )
            db.add(role)
        role.tenant_id = project.tenant_id
        role.company_id = project.company_id
        role.org_path = project.org_path
        role.user_name = payload["user_name"]
        role.subcontractor_id = payload["subcontractor_id"]
        role.status = "active"

    attachments = {
        "items": [
            {
                "file_id": "F-DEMO-P002-DISCOVERY",
                "phase": "discovery",
                "content_type": "image/jpeg",
                "file_name": "demo-p002-hazard.jpg",
                "url": "/api/v1/files/F-DEMO-P002-DISCOVERY",
                "sha256": "demo-seed-placeholder",
                "size_bytes": 0,
                "uploaded_by": "U-GC-01",
                "uploaded_at": datetime.datetime.utcnow().isoformat(),
            }
        ]
    }
    hazard = db.query(Hazard).filter(Hazard.hazard_id == "H-DEMO-P002-001").first()
    if hazard is None:
        hazard = Hazard(
            hazard_id="H-DEMO-P002-001",
            tenant_id=project.tenant_id,
            company_id=project.company_id,
            org_path=project.org_path,
            project_id="P002",
            subcontractor_id="S003",
            hazard_type="临边防护",
            hazard_level="major",
            description="武汉长江中心基坑东侧临边防护缺失，存在高处坠落风险。",
            status="open",
            due_date=today + datetime.timedelta(days=7),
            is_major=True,
            discovered_by_user_id="U-GC-01",
            location="基坑东侧",
            attachments=attachments,
            work_order_id="WO-DEMO-P002-001",
        )
        db.add(hazard)
    else:
        hazard.tenant_id = project.tenant_id
        hazard.company_id = project.company_id
        hazard.org_path = project.org_path
        hazard.project_id = "P002"
        hazard.subcontractor_id = "S003"
        hazard.status = "open"
        hazard.attachments = attachments
        hazard.work_order_id = "WO-DEMO-P002-001"

    order = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.work_order_id == "WO-DEMO-P002-001").first()
    if order is None:
        order = SafetyWorkOrder(
            work_order_id="WO-DEMO-P002-001",
            tenant_id=project.tenant_id,
            company_id=project.company_id,
            org_path=project.org_path,
            work_order_type="hazard_rectification",
            source_type="hazard",
            source_id="H-DEMO-P002-001",
            project_id="P002",
            subcontractor_id="S003",
            title="武汉长江中心临边防护整改演示单",
            description="由总包安全员上传隐患后自动创建，供审批派发、分包整改、总包验收演示。",
            priority="high",
            status="pending_confirm",
            due_time=datetime.datetime.combine(today + datetime.timedelta(days=7), datetime.time(hour=18)),
            attachments=attachments,
        )
        db.add(order)
    else:
        order.tenant_id = project.tenant_id
        order.company_id = project.company_id
        order.org_path = project.org_path
        order.work_order_type = "hazard_rectification"
        order.source_type = "hazard"
        order.source_id = "H-DEMO-P002-001"
        order.project_id = "P002"
        order.subcontractor_id = "S003"
        order.title = "武汉长江中心临边防护整改演示单"
        order.description = "由总包安全员上传隐患后自动创建，供审批派发、分包整改、总包验收演示。"
        order.priority = "high"
        order.status = "pending_confirm"
        order.due_time = datetime.datetime.combine(today + datetime.timedelta(days=7), datetime.time(hour=18))
        order.attachments = attachments

    flow_log = (
        db.query(WorkOrderFlowLog)
        .filter(
            WorkOrderFlowLog.work_order_id == "WO-DEMO-P002-001",
            WorkOrderFlowLog.action == "create",
        )
        .first()
    )
    if flow_log is None:
        flow_log = WorkOrderFlowLog(
            work_order_id="WO-DEMO-P002-001",
            from_status=None,
            to_status="pending_confirm",
            action="create",
            operator_user_id="U-GC-01",
            operator_role="gc_safety_officer",
            comment="演示 seed 自动创建整改工单",
            attachments=attachments,
        )
        db.add(flow_log)
    else:
        flow_log.from_status = None
        flow_log.to_status = "pending_confirm"
        flow_log.operator_user_id = "U-GC-01"
        flow_log.operator_role = "gc_safety_officer"
        flow_log.attachments = attachments

    db.commit()


def seed_demo_data() -> None:
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()

    try:
        if db.query(Tenant).filter(Tenant.tenant_id == "CSCEC").first() is not None:
            seed_metrics(db)
            seed_accident_cases(db)
            seed_work_order_workflow_demo(db)
            seed_rbac_foundation(db, tenant_id="CSCEC", company_id="CSCEC")
            sync_agent_prompt_versions(db)
            enrichment = seed_mock_enrichment(db, tenant_id="CSCEC", company_id="CSCEC")
            print("=== Demo data already exists; incremental enrichment applied ===")
            print("=== Metric catalog synchronized ===")
            print("=== Accident cases synchronized ===")
            print("=== Work order workflow demo synchronized ===")
            print("=== RBAC foundation synchronized ===")
            print("=== Agent prompt versions synchronized ===")
            print(f"=== Mock enrichment: {enrichment} ===")
            return

        today = datetime.date.today()

        # --- Tenant ---
        tenant = Tenant(tenant_id="CSCEC", tenant_name="中建集团")
        db.add(tenant)

        # --- Projects ---
        projects_data = [
            {"project_id": "P001", "project_name": "上海临港TOD综合开发项目", "project_type": "housing", "construction_phase": "main_structure", "schedule_pressure_index": 35, "night_shift_days": 5, "cross_operation_count": 3},
            {"project_id": "P002", "project_name": "武汉长江中心", "project_type": "housing", "construction_phase": "foundation", "schedule_pressure_index": 10, "night_shift_days": 0, "cross_operation_count": 1},
            {"project_id": "P003", "project_name": "深圳地铁13号线", "project_type": "infrastructure", "construction_phase": "main_structure", "schedule_pressure_index": 25, "night_shift_days": 3, "cross_operation_count": 2},
        ]
        projects = []
        for p in projects_data:
            proj = Project(
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=f"CSCEC/CSCEC-8B/EAST-REGION/{p['project_id']}",
                region="华东",
                status="active",
                **p,
                start_date=today - datetime.timedelta(days=365),
                end_date=today + datetime.timedelta(days=365),
            )
            db.add(proj)
            projects.append(proj)

        # --- Subcontractors ---
        subs_data = [
            {"subcontractor_id": "S001", "subcontractor_name": "华东建设劳务有限公司", "qualification": "一级", "safety_license_status": "valid", "credit_score": 85},
            {"subcontractor_id": "S002", "subcontractor_name": "中建安装劳务有限公司", "qualification": "一级", "safety_license_status": "valid", "credit_score": 90},
            {"subcontractor_id": "S003", "subcontractor_name": "广东宏大建设有限公司", "qualification": "二级", "safety_license_status": "valid", "accident_history_count": 2, "credit_score": 60},
        ]
        subcontractors = []
        for s in subs_data:
            sub = Subcontractor(
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=f"CSCEC/CSCEC-8B/EAST-REGION/{s['subcontractor_id']}",
                **s,
            )
            db.add(sub)
            subcontractors.append(sub)

        # --- Workers ---
        workers_data = [
            {"worker_id": "W001", "project_id": "P001", "subcontractor_id": "S001", "worker_name_masked": "张**", "work_type": "电工", "special_cert_status": "valid", "exam_score": 85, "violation_count_30d": 0, "entry_days": 30},
            {"worker_id": "W002", "project_id": "P001", "subcontractor_id": "S001", "worker_name_masked": "李**", "work_type": "架子工", "special_cert_status": "valid", "exam_score": 72, "violation_count_30d": 1, "entry_days": 60},
            {"worker_id": "W003", "project_id": "P001", "subcontractor_id": "S002", "worker_name_masked": "王**", "work_type": "塔吊司机", "special_cert_status": "expired", "exam_score": 55, "violation_count_30d": 3, "entry_days": 90},
            {"worker_id": "W004", "project_id": "P002", "subcontractor_id": "S001", "worker_name_masked": "赵**", "work_type": "焊工", "special_cert_status": "valid", "exam_score": 90, "violation_count_30d": 0, "entry_days": 15},
            {"worker_id": "W005", "project_id": "P002", "subcontractor_id": "S003", "worker_name_masked": "刘**", "work_type": "普工", "special_cert_status": "valid", "health_check_status": "expired", "exam_score": 48, "violation_count_30d": 4, "entry_days": 45},
            {"worker_id": "W006", "project_id": "P003", "subcontractor_id": "S002", "worker_name_masked": "陈**", "work_type": "电工", "special_cert_status": "valid", "exam_score": 78, "violation_count_30d": 0, "entry_days": 3},
            {"worker_id": "W007", "project_id": "P003", "subcontractor_id": "S003", "worker_name_masked": "周**", "work_type": "起重机司机", "special_cert_status": "missing", "exam_score": 62, "violation_count_30d": 2, "entry_days": 120},
            {"worker_id": "W008", "project_id": "P001", "subcontractor_id": "S002", "worker_name_masked": "吴**", "work_type": "信号工", "special_cert_status": "valid", "exam_score": 80, "violation_count_30d": 0, "entry_days": 200},
        ]
        workers = []
        for w in workers_data:
            worker = Worker(
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=f"CSCEC/CSCEC-8B/EAST-REGION/{w['project_id']}/{w['subcontractor_id']}",
                team_id=f"T-{w['subcontractor_id']}",
                violation_count_180d=w.get("violation_count_30d", 0) * 2,
                age=random.randint(25, 55),
                **w,
            )
            db.add(worker)
            workers.append(worker)

        # --- Hazards ---
        hazards_data = [
            {"hazard_id": "H001", "project_id": "P001", "subcontractor_id": "S001", "hazard_type": "临边防护", "hazard_level": "general", "description": "5层临边防护缺失", "status": "open", "due_date": today + datetime.timedelta(days=5), "is_major": False},
            {"hazard_id": "H002", "project_id": "P001", "subcontractor_id": "S002", "hazard_type": "脚手架", "hazard_level": "major", "description": "外架连墙件数量不足", "status": "open", "due_date": today - datetime.timedelta(days=3), "is_major": True},
            {"hazard_id": "H003", "project_id": "P001", "subcontractor_id": "S001", "hazard_type": "临时用电", "hazard_level": "general", "description": "配电箱未接地", "status": "closed", "due_date": today - datetime.timedelta(days=10), "close_date": today - datetime.timedelta(days=8), "is_major": False},
            {"hazard_id": "H004", "project_id": "P002", "subcontractor_id": "S001", "hazard_type": "高处作业", "hazard_level": "general", "description": "安全网破损", "status": "open", "due_date": today + datetime.timedelta(days=7), "is_major": False},
            {"hazard_id": "H005", "project_id": "P002", "subcontractor_id": "S003", "hazard_type": "基坑", "hazard_level": "major", "description": "基坑边坡局部开裂", "status": "open", "due_date": today - datetime.timedelta(days=1), "is_major": True},
            {"hazard_id": "H006", "project_id": "P003", "subcontractor_id": "S002", "hazard_type": "机械伤害", "hazard_level": "general", "description": "钢筋加工区防护不足", "status": "open", "due_date": today + datetime.timedelta(days=3), "is_major": False},
            {"hazard_id": "H007", "project_id": "P003", "subcontractor_id": "S003", "hazard_type": "高处坠落", "hazard_level": "major", "description": "地铁站台层临边防护缺失", "status": "open", "due_date": today - datetime.timedelta(days=5), "is_major": True},
        ]
        for h in hazards_data:
            hazard = Hazard(
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=f"CSCEC/CSCEC-8B/EAST-REGION/{h['project_id']}",
                **h,
            )
            db.add(hazard)

        # --- Equipment ---
        equipment_data = [
            {"equipment_id": "E001", "project_id": "P001", "subcontractor_id": "S002", "equipment_type": "塔吊", "equipment_name": "QTZ80塔式起重机", "inspection_due_date": today - datetime.timedelta(days=15), "use_status": "in_use", "is_special": True},
            {"equipment_id": "E002", "project_id": "P001", "subcontractor_id": "S001", "equipment_type": "施工升降机", "equipment_name": "SC200/200施工升降机", "inspection_due_date": today + datetime.timedelta(days=30), "use_status": "in_use", "is_special": True},
            {"equipment_id": "E003", "project_id": "P002", "subcontractor_id": "S001", "equipment_type": "吊篮", "equipment_name": "ZLP630高处作业吊篮", "inspection_due_date": today + datetime.timedelta(days=60), "use_status": "in_use", "is_special": False},
            {"equipment_id": "E004", "project_id": "P003", "subcontractor_id": "S003", "equipment_type": "挖掘机", "equipment_name": "CAT320挖掘机", "inspection_due_date": today + datetime.timedelta(days=90), "use_status": "in_use", "is_special": False},
        ]
        for e in equipment_data:
            eq = Equipment(
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=f"CSCEC/CSCEC-8B/EAST-REGION/{e['project_id']}",
                **e,
            )
            db.add(eq)

        db.commit()

        # --- Calculate Profiles ---
        # Project risk profiles
        for proj in projects:
            hazards = db.query(Hazard).filter(Hazard.project_id == proj.project_id).all()
            overdue = sum(1 for h in hazards if h.due_date and h.due_date < today and h.status != "closed")
            major_overdue = sum(1 for h in hazards if h.is_major and h.due_date and h.due_date < today and h.status != "closed")
            eq_overdue = sum(1 for e in equipment_data if e["project_id"] == proj.project_id and e["inspection_due_date"] < today and e["use_status"] == "in_use")

            profile = calculate_project_profile(
                hazard_overdue_count=overdue,
                major_hazard_overdue_count=major_overdue,
                equipment_overdue_count=eq_overdue,
                schedule_pressure_index=proj.schedule_pressure_index,
                project_type=proj.project_type,
                night_shift_days=proj.night_shift_days,
                cross_operation_count=proj.cross_operation_count,
            )
            db.add(ProjectRiskProfile(
                project_id=proj.project_id,
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=proj.org_path,
                calc_date=today,
                total_risk_score=profile.total_risk_score,
                risk_level=profile.risk_level,
                data_completeness=profile.data_completeness,
                confidence_level="medium_high",
                hazard_rectification_score=min(100.0, overdue * 15 + major_overdue * 10),
                equipment_mechanical_score=min(100.0, eq_overdue * 25),
                schedule_pressure_score=min(100.0, proj.schedule_pressure_index),
                subcontractor_transfer_score=min(100.0, proj.cross_operation_count * 12),
                behavior_risk_score=min(100.0, proj.night_shift_days * 4),
                risk_tags={"tags": profile.risk_tags},
                strong_rule_flags={"evidence": profile.evidence},
                explanation=f"项目{proj.project_name}当前风险等级{profile.risk_level}, 风险分{profile.total_risk_score}",
                suggestion="优先闭环重大隐患、复核特种设备检验有效期，并加强交叉作业安全巡检。",
                model_version="v1.0",
            ))

            # Rule trigger logs
            if major_overdue > 0:
                db.add(RuleTriggerLog(
                    rule_id="SR-PROJ-001", tenant_id="CSCEC", org_path=proj.org_path,
                    object_type="project", object_id=proj.project_id, project_id=proj.project_id,
                    trigger_condition=f"major_hazard_overdue_count={major_overdue}",
                    evidence={"count": major_overdue}, risk_action="upgrade_to_high", severity="high",
                ))
            if eq_overdue > 0:
                db.add(RuleTriggerLog(
                    rule_id="SR-PROJ-004", tenant_id="CSCEC", org_path=proj.org_path,
                    object_type="equipment", object_id="E001", project_id=proj.project_id,
                    trigger_condition=f"equipment_overdue_in_use={eq_overdue}",
                    evidence={"count": eq_overdue}, risk_action="stop_and_inspect", severity="high",
                ))

        # Worker risk profiles
        for w in workers:
            profile = calculate_worker_profile(
                exam_score=w.exam_score, violation_count_30d=w.violation_count_30d,
                special_cert_status=w.special_cert_status, health_check_status=w.health_check_status,
                entry_days=w.entry_days,
            )
            if profile.total_risk_score > 0 or profile.risk_tags:
                db.add(WorkerRiskProfile(
                    worker_id=w.worker_id,
                    project_id=w.project_id,
                    subcontractor_id=w.subcontractor_id,
                    tenant_id="CSCEC",
                    company_id="CSCEC",
                    org_path=w.org_path,
                    calc_date=today,
                    total_risk_score=profile.total_risk_score,
                    risk_level=profile.risk_level,
                    data_completeness=profile.data_completeness,
                    confidence_level="medium",
                    exam_risk_score=max(0.0, 60 - (w.exam_score or 60)),
                    violation_risk_score=min(100.0, w.violation_count_30d * 20),
                    qualification_risk_score=100.0 if w.special_cert_status in ("expired", "missing") else 0.0,
                    health_adaptation_score=60.0 if w.health_check_status == "expired" else 0.0,
                    operation_context_score=30.0 if w.entry_days < 7 else 0.0,
                    risk_tags={"tags": profile.risk_tags},
                    strong_rule_flags={"evidence": profile.evidence},
                    explanation=f"工人{w.worker_name_masked}风险等级{profile.risk_level}",
                    suggestion="复核证书有效性、培训记录与近期违规情况。",
                    model_version="v1.0",
                ))

        # Subcontractor risk profiles
        for sub in subcontractors:
            sub_workers = [w for w in workers if w.subcontractor_id == sub.subcontractor_id]
            project_id = sub_workers[0].project_id if sub_workers else "P001"
            sub_hazards = [h for h in hazards_data if h["subcontractor_id"] == sub.subcontractor_id]
            high_risk_count = sum(1 for w in sub_workers if w.violation_count_30d >= 3 or w.special_cert_status == "expired" or (w.exam_score and w.exam_score < 60))
            high_risk_ratio = high_risk_count / max(1, len(sub_workers))
            overdue_hazards = sum(1 for h in sub_hazards if h.get("due_date") and h["due_date"] < today and h.get("status") != "closed")
            major_overdue = sum(1 for h in sub_hazards if h.get("is_major") and h.get("due_date") and h["due_date"] < today and h.get("status") != "closed")

            profile = calculate_subcontractor_profile(
                hazard_overdue_count=overdue_hazards,
                major_hazard_overdue_count=major_overdue,
                high_risk_worker_ratio=high_risk_ratio,
                safety_license_status=sub.safety_license_status,
                accident_history_count=sub.accident_history_count,
            )
            db.add(SubcontractorRiskProfile(
                subcontractor_id=sub.subcontractor_id,
                project_id=project_id,
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=sub.org_path,
                calc_date=today,
                total_risk_score=profile.total_risk_score,
                risk_level=profile.risk_level,
                data_completeness=profile.data_completeness,
                confidence_level="medium",
                qualification_risk_score=100.0 if sub.safety_license_status == "expired" else 0.0,
                worker_management_score=high_risk_ratio * 100,
                hazard_rectification_score=min(100.0, overdue_hazards * 20),
                violation_risk_score=min(100.0, sum(w["violation_count_30d"] for w in workers_data if w["subcontractor_id"] == sub.subcontractor_id) * 10),
                equipment_management_score=20.0 if sub.subcontractor_id == "S003" else 5.0,
                accident_credit_score=min(100.0, sub.accident_history_count * 30),
                high_risk_worker_ratio=high_risk_ratio,
                overdue_rectification_ratio=overdue_hazards / max(1, len(sub_hazards)),
                risk_tags={"tags": profile.risk_tags},
                strong_rule_flags={"evidence": profile.evidence},
                explanation=f"分包商{sub.subcontractor_name}风险等级{profile.risk_level}",
                suggestion="关注许可证状态、超期隐患和高风险工人管理。",
                model_version="v1.0",
            ))

        # --- Work Orders ---
        work_orders_data = [
            {"work_order_id": "WO001", "work_order_type": "rectification", "project_id": "P001", "subcontractor_id": "S002", "title": "外架连墙件加固整改", "description": "H002: 外架连墙件数量不足，需立即补装", "status": "dispatched", "priority": "high", "due_time": today + datetime.timedelta(days=2), "rule_id": "SR-PROJ-001"},
            {"work_order_id": "WO002", "work_order_type": "equipment_inspection", "project_id": "P001", "equipment_id": "E001", "title": "塔吊超期未检停用核查", "description": "QTZ80塔吊检验有效期已过，需立即停用并安排检验", "status": "pending_confirm", "priority": "critical", "due_time": today + datetime.timedelta(days=1), "rule_id": "SR-PROJ-004"},
            {"work_order_id": "WO003", "work_order_type": "worker_training", "project_id": "P001", "worker_id": "W003", "title": "塔吊司机证书过期复训", "description": "工人王**特种作业证已过期，暂停作业并安排复训", "status": "dispatched", "priority": "high", "due_time": today + datetime.timedelta(days=7), "rule_id": "SR-WORKER-001"},
            {"work_order_id": "WO004", "work_order_type": "rectification", "project_id": "P002", "subcontractor_id": "S003", "title": "基坑边坡加固整改", "description": "H005: 基坑边坡局部开裂，需立即支护加固", "status": "processing", "priority": "critical", "due_time": today + datetime.timedelta(days=1), "rule_id": "SR-PROJ-001"},
            {"work_order_id": "WO005", "work_order_type": "worker_training", "project_id": "P002", "worker_id": "W005", "title": "高频违规工人专项培训", "description": "工人刘**30天内违规4次，推送高处作业和临边防护专项培训", "status": "pending_confirm", "priority": "high", "due_time": today + datetime.timedelta(days=5), "rule_id": "SR-WORKER-005"},
        ]
        for wo in work_orders_data:
            order = SafetyWorkOrder(
                tenant_id="CSCEC",
                company_id="CSCEC",
                org_path=f"CSCEC/CSCEC-8B/EAST-REGION/{wo['project_id']}",
                **wo,
            )
            db.add(order)

        # --- Metric Catalog & enrichment modules ---
        seed_metrics(db)
        seed_accident_cases(db)
        seed_work_order_workflow_demo(db)
        seed_rbac_foundation(db, tenant_id="CSCEC", company_id="CSCEC")
        sync_agent_prompt_versions(db)
        enrichment = seed_mock_enrichment(db, tenant_id="CSCEC", company_id="CSCEC")

        db.commit()
        print("=== Seed data inserted successfully ===")
        print(f"=== Mock enrichment: {enrichment} ===")
        print(f"  Tenant: 1")
        print(f"  Projects: {len(projects)}")
        print(f"  Subcontractors: {len(subcontractors)}")
        print(f"  Workers: {len(workers)}")
        print(f"  Hazards: {len(hazards_data)}")
        print(f"  Equipment: {len(equipment_data)}")
        print(f"  Work Orders: {len(work_orders_data)}")
        print(f"  Metrics: {db.query(MetricCatalog).count()}")

    except Exception as e:
        db.rollback()
        print(f"Error seeding data: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
