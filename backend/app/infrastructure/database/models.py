import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, Text, JSON, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database.session import Base


class Tenant(Base):
    __tablename__ = "tenant"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active")
    config_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Project(Base):
    __tablename__ = "project"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_type: Mapped[str] = mapped_column(String(64), default="housing")
    construction_phase: Mapped[str] = mapped_column(String(64), default="main_structure")
    region: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), default="active")
    start_date: Mapped[datetime.date | None] = mapped_column(Date)
    end_date: Mapped[datetime.date | None] = mapped_column(Date)
    schedule_pressure_index: Mapped[float] = mapped_column(Float, default=0)
    night_shift_days: Mapped[int] = mapped_column(Integer, default=0)
    cross_operation_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Subcontractor(Base):
    __tablename__ = "subcontractor"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subcontractor_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_path: Mapped[str] = mapped_column(String(512))
    subcontractor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    qualification: Mapped[str | None] = mapped_column(String(128))
    safety_license_status: Mapped[str] = mapped_column(String(32), default="valid")
    accident_history_count: Mapped[int] = mapped_column(Integer, default=0)
    credit_score: Mapped[float] = mapped_column(Float, default=100)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Worker(Base):
    __tablename__ = "worker"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_path: Mapped[str] = mapped_column(String(512))
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    subcontractor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    team_id: Mapped[str | None] = mapped_column(String(64))
    worker_name_masked: Mapped[str] = mapped_column(String(128))
    work_type: Mapped[str | None] = mapped_column(String(64))
    age: Mapped[int | None] = mapped_column(Integer)
    special_cert_status: Mapped[str] = mapped_column(String(32), default="valid")
    health_check_status: Mapped[str] = mapped_column(String(32), default="valid")
    exam_score: Mapped[float | None] = mapped_column(Float)
    violation_count_30d: Mapped[int] = mapped_column(Integer, default=0)
    violation_count_180d: Mapped[int] = mapped_column(Integer, default=0)
    entry_days: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Hazard(Base):
    __tablename__ = "hazard"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hazard_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_path: Mapped[str] = mapped_column(String(512))
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subcontractor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    worker_id: Mapped[str | None] = mapped_column(String(64))
    equipment_id: Mapped[str | None] = mapped_column(String(64))
    hazard_type: Mapped[str] = mapped_column(String(64))
    hazard_level: Mapped[str] = mapped_column(String(32), default="general")
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="open")
    due_date: Mapped[datetime.date | None] = mapped_column(Date)
    close_date: Mapped[datetime.date | None] = mapped_column(Date)
    is_major: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_path: Mapped[str] = mapped_column(String(512))
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    subcontractor_id: Mapped[str | None] = mapped_column(String(64))
    equipment_type: Mapped[str] = mapped_column(String(64))
    equipment_name: Mapped[str] = mapped_column(String(255))
    inspection_due_date: Mapped[datetime.date | None] = mapped_column(Date)
    maintenance_status: Mapped[str] = mapped_column(String(32), default="normal")
    use_status: Mapped[str] = mapped_column(String(32), default="in_use")
    is_special: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ProjectRiskProfile(Base):
    __tablename__ = "project_risk_profile"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    org_path: Mapped[str] = mapped_column(String(512))
    calc_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    data_completeness: Mapped[float | None] = mapped_column(Float)
    confidence_level: Mapped[str | None] = mapped_column(String(32))
    hazard_rectification_score: Mapped[float | None] = mapped_column(Float)
    equipment_mechanical_score: Mapped[float | None] = mapped_column(Float)
    schedule_pressure_score: Mapped[float | None] = mapped_column(Float)
    subcontractor_transfer_score: Mapped[float | None] = mapped_column(Float)
    behavior_risk_score: Mapped[float | None] = mapped_column(Float)
    safety_investment_score: Mapped[float | None] = mapped_column(Float)
    management_staff_score: Mapped[float | None] = mapped_column(Float)
    dynamic_factor: Mapped[float | None] = mapped_column(Float, default=1.00)
    strong_rule_flags: Mapped[dict | None] = mapped_column(JSON)
    risk_tags: Mapped[dict | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class WorkerRiskProfile(Base):
    __tablename__ = "worker_risk_profile"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    worker_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    subcontractor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    org_path: Mapped[str] = mapped_column(String(512))
    calc_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    data_completeness: Mapped[float | None] = mapped_column(Float)
    confidence_level: Mapped[str | None] = mapped_column(String(32))
    exam_risk_score: Mapped[float | None] = mapped_column(Float)
    violation_risk_score: Mapped[float | None] = mapped_column(Float)
    qualification_risk_score: Mapped[float | None] = mapped_column(Float)
    health_adaptation_score: Mapped[float | None] = mapped_column(Float)
    operation_context_score: Mapped[float | None] = mapped_column(Float)
    dynamic_factor: Mapped[float | None] = mapped_column(Float, default=1.00)
    strong_rule_flags: Mapped[dict | None] = mapped_column(JSON)
    risk_tags: Mapped[dict | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class SubcontractorRiskProfile(Base):
    __tablename__ = "subcontractor_risk_profile"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subcontractor_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    org_path: Mapped[str] = mapped_column(String(512))
    calc_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    total_risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    data_completeness: Mapped[float | None] = mapped_column(Float)
    confidence_level: Mapped[str | None] = mapped_column(String(32))
    qualification_risk_score: Mapped[float | None] = mapped_column(Float)
    worker_management_score: Mapped[float | None] = mapped_column(Float)
    hazard_rectification_score: Mapped[float | None] = mapped_column(Float)
    violation_risk_score: Mapped[float | None] = mapped_column(Float)
    equipment_management_score: Mapped[float | None] = mapped_column(Float)
    safety_investment_score: Mapped[float | None] = mapped_column(Float)
    accident_credit_score: Mapped[float | None] = mapped_column(Float)
    high_risk_worker_ratio: Mapped[float | None] = mapped_column(Float)
    overdue_rectification_ratio: Mapped[float | None] = mapped_column(Float)
    strong_rule_flags: Mapped[dict | None] = mapped_column(JSON)
    risk_tags: Mapped[dict | None] = mapped_column(JSON)
    explanation: Mapped[str | None] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text)
    model_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class RuleTriggerLog(Base):
    __tablename__ = "rule_trigger_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_path: Mapped[str] = mapped_column(String(512))
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    trigger_condition: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSON)
    risk_action: Mapped[str | None] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(String(32), default="high")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class SafetyWorkOrder(Base):
    __tablename__ = "safety_work_order"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    work_order_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    org_path: Mapped[str] = mapped_column(String(512))
    work_order_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_type: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[str | None] = mapped_column(String(128))
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    subcontractor_id: Mapped[str | None] = mapped_column(String(64))
    worker_id: Mapped[str | None] = mapped_column(String(64))
    equipment_id: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(32), default="normal")
    status: Mapped[str] = mapped_column(String(32), default="pending_confirm")
    responsible_user_id: Mapped[str | None] = mapped_column(String(64))
    review_user_id: Mapped[str | None] = mapped_column(String(64))
    due_time: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    review_time: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    close_time: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    escalation_history: Mapped[dict | None] = mapped_column(JSON)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSON)
    attachments: Mapped[dict | None] = mapped_column(JSON)
    rule_id: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(32))
    agent_task_id: Mapped[str | None] = mapped_column(String(64))
    external_system: Mapped[str | None] = mapped_column(String(64))
    external_work_order_id: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AgentTaskLog(Base):
    __tablename__ = "agent_task_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    org_path: Mapped[str] = mapped_column(String(512))
    user_id: Mapped[str] = mapped_column(String(64))
    agent_name: Mapped[str] = mapped_column(String(64))
    intent: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(64))
    model_version: Mapped[str | None] = mapped_column(String(64))
    input_summary: Mapped[str | None] = mapped_column(Text)
    output_summary: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[dict | None] = mapped_column(JSON)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class MetricCatalog(Base):
    __tablename__ = "metric_catalog"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    metric_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_definition: Mapped[str] = mapped_column(Text)
    calculation_formula: Mapped[str | None] = mapped_column(Text)
    statistical_period: Mapped[str | None] = mapped_column(String(64))
    dimensions: Mapped[dict | None] = mapped_column(JSON)
    source_tables: Mapped[dict | None] = mapped_column(JSON)
    source_fields: Mapped[dict | None] = mapped_column(JSON)
    filters: Mapped[dict | None] = mapped_column(JSON)
    permission_level: Mapped[str | None] = mapped_column(String(64))
    owner_department: Mapped[str | None] = mapped_column(String(128))
    metric_version: Mapped[str] = mapped_column(String(32), default="v1.0")
    status: Mapped[str] = mapped_column(String(32), default="enabled")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AgentTaskCheckpoint(Base):
    __tablename__ = "agent_task_checkpoint"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(32))
    context_json: Mapped[dict | None] = mapped_column(JSON)
    sub_task_json: Mapped[dict | None] = mapped_column(JSON)
    result_ref: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class ProfileCalcDetail(Base):
    __tablename__ = "profile_calc_detail"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    calc_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(64))
    dimension_code: Mapped[str] = mapped_column(String(64))
    dimension_score: Mapped[float | None] = mapped_column(Float)
    dimension_weight: Mapped[float | None] = mapped_column(Float)
    evidence: Mapped[dict | None] = mapped_column(JSON)
    dynamic_factors: Mapped[dict | None] = mapped_column(JSON)
    rule_triggers: Mapped[dict | None] = mapped_column(JSON)
    metric_version: Mapped[str | None] = mapped_column(String(32))
    rule_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


# Indexes for profile tables
Index("idx_project_date", ProjectRiskProfile.project_id, ProjectRiskProfile.calc_date, unique=True)
Index("idx_worker_project_date", WorkerRiskProfile.worker_id, WorkerRiskProfile.project_id, WorkerRiskProfile.calc_date, unique=True)
Index("idx_sub_project_date", SubcontractorRiskProfile.subcontractor_id, SubcontractorRiskProfile.project_id, SubcontractorRiskProfile.calc_date, unique=True)
