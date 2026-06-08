import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Date, Text, JSON, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.infrastructure.database.session import Base


def _company_id_default(context) -> str:
    return context.get_current_parameters().get("tenant_id") or "CSCEC"


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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    discovered_by_user_id: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[str | None] = mapped_column(String(255))
    attachments: Mapped[dict | None] = mapped_column(JSON)
    work_order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class Equipment(Base):
    __tablename__ = "equipment"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    equipment_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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


class UserAccount(Base):
    __tablename__ = "user_account"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", name="uk_user_account_tenant_user"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_name: Mapped[str] = mapped_column(String(128), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255))
    password_hash: Mapped[str | None] = mapped_column(String(255))
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="company")
    authorized_project_ids: Mapped[list | None] = mapped_column(JSON)
    subcontractor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )


class AuthRole(Base):
    __tablename__ = "auth_role"
    __table_args__ = (UniqueConstraint("tenant_id", "role_code", name="uk_auth_role_tenant_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_name: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="company")
    permissions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )


class UserRole(Base):
    __tablename__ = "user_role"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "role_id", "project_id", name="uk_user_role_scope"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, default="", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )


class ProjectUser(Base):
    __tablename__ = "project_user"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", "role_code", name="uk_project_user_role"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False)
    project_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_name: Mapped[str] = mapped_column(String(128), nullable=False)
    role_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    subcontractor_id: Mapped[str | None] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class WorkOrderFlowLog(Base):
    __tablename__ = "work_order_flow_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    work_order_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operator_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    operator_role: Mapped[str] = mapped_column(String(64), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    attachments: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class AgentTaskLog(Base):
    __tablename__ = "agent_task_log"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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


class AgentDagRun(Base):
    __tablename__ = "agent_dag_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    target_agent: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned", index=True)
    need_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class AgentDagStepRun(Base):
    __tablename__ = "agent_dag_step_run"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    step_run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_code: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned", index=True)
    will_execute: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    input_summary: Mapped[dict | None] = mapped_column(JSON)
    output_summary: Mapped[dict | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class AgentApprovalRequest(Base):
    __tablename__ = "agent_approval_request"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    approval_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    step_run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False)
    request_user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    requested_tool: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_action: Mapped[str] = mapped_column(String(128), nullable=False)
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    target_id: Mapped[str | None] = mapped_column(String(128), index=True)
    payload_summary: Mapped[str | None] = mapped_column(Text)
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    reason: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    approver_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    approval_comment: Mapped[str | None] = mapped_column(Text)
    executor_user_id: Mapped[str | None] = mapped_column(String(64), index=True)
    executed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    execution_result: Mapped[dict | None] = mapped_column(JSON)
    execution_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )
    approved_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    rejected_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    expires_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class AgentNl2sqlAudit(Base):
    __tablename__ = "agent_nl2sql_audit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question: Mapped[str | None] = mapped_column(Text)
    candidate_sql: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_sql: Mapped[str | None] = mapped_column(Text)
    allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reject_reason: Mapped[str | None] = mapped_column(Text)
    tables_used: Mapped[dict | None] = mapped_column(JSON)
    fields_used: Mapped[dict | None] = mapped_column(JSON)
    scope_injected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    execution_status: Mapped[str] = mapped_column(String(32), default="audited", nullable=False)
    result_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    result_field_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_error: Mapped[str | None] = mapped_column(Text)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class MetricCatalog(Base):
    __tablename__ = "metric_catalog"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default="CSCEC")
    project_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    metric_code: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_definition: Mapped[str] = mapped_column(Text)
    calculation_formula: Mapped[str | None] = mapped_column(Text)
    statistical_period: Mapped[str | None] = mapped_column(String(64))
    dimensions: Mapped[dict | None] = mapped_column(JSON)
    source_tables: Mapped[dict | None] = mapped_column(JSON)
    source_fields: Mapped[dict | None] = mapped_column(JSON)
    filters: Mapped[dict | None] = mapped_column(JSON)
    aliases: Mapped[dict | None] = mapped_column(JSON)
    permission_level: Mapped[str | None] = mapped_column(String(64))
    owner_department: Mapped[str | None] = mapped_column(String(128))
    metric_version: Mapped[str] = mapped_column(String(32), default="v1.0")
    status: Mapped[str] = mapped_column(String(32), default="enabled")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AccidentCaseLibrary(Base):
    __tablename__ = "accident_case_library"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    accident_case_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    accident_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    project_type: Mapped[str | None] = mapped_column(String(64))
    operation_scene: Mapped[str | None] = mapped_column(String(64))
    direct_cause: Mapped[str | None] = mapped_column(Text)
    indirect_cause: Mapped[str | None] = mapped_column(Text)
    involved_subjects: Mapped[dict | None] = mapped_column(JSON)
    warning_indicators: Mapped[dict | None] = mapped_column(JSON)
    rectification_measures: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[dict | None] = mapped_column(JSON)
    embedding_version: Mapped[str | None] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AgentSessionSummary(Base):
    __tablename__ = "agent_session_summary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    summary: Mapped[str | None] = mapped_column(Text)
    message_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_message_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AgentTaskCheckpoint(Base):
    __tablename__ = "agent_task_checkpoint"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    task_type: Mapped[str | None] = mapped_column(String(64))
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str | None] = mapped_column(String(32))
    context_json: Mapped[dict | None] = mapped_column(JSON)
    sub_task_json: Mapped[dict | None] = mapped_column(JSON)
    result_ref: Mapped[str | None] = mapped_column(String(255))
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AgentPromptVersion(Base):
    __tablename__ = "agent_prompt_version"
    __table_args__ = (
        UniqueConstraint("agent_code", "prompt_version", name="uk_agent_prompt_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_path: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)


class AgentFeedback(Base):
    __tablename__ = "agent_feedback"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    feedback_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    feedback_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rating: Mapped[int | None] = mapped_column(Integer)
    feedback_reason: Mapped[str | None] = mapped_column(String(255))
    original_output: Mapped[dict | None] = mapped_column(JSON)
    corrected_output: Mapped[dict | None] = mapped_column(JSON)
    correction_text: Mapped[str | None] = mapped_column(Text)
    related_work_order_id: Mapped[str | None] = mapped_column(String(64), index=True)
    label_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    used_for_prompt_tuning: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    used_for_finetune: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)


class WebhookDeliveryLog(Base):
    __tablename__ = "webhook_delivery_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    delivery_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
    org_path: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_id: Mapped[str | None] = mapped_column(String(64), index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False, default="http")
    target_url_masked: Mapped[str | None] = mapped_column(String(512))
    request_payload: Mapped[dict | None] = mapped_column(JSON)
    response_status_code: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    need_human_review: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    triggered_by: Mapped[str | None] = mapped_column(String(64))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)
    delivered_at: Mapped[datetime.datetime | None] = mapped_column(DateTime)


class ProfileCalcDetail(Base):
    __tablename__ = "profile_calc_detail"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    calc_batch_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    profile_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str] = mapped_column(String(64), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True, default=_company_id_default)
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
Index("idx_project_company_project", Project.company_id, Project.project_id)
Index("idx_worker_company_project", Worker.company_id, Worker.project_id)
Index("idx_hazard_company_project", Hazard.company_id, Hazard.project_id)
Index("idx_equipment_company_project", Equipment.company_id, Equipment.project_id)
Index("idx_work_order_company_project", SafetyWorkOrder.company_id, SafetyWorkOrder.project_id)
Index("idx_rule_trigger_company_project", RuleTriggerLog.company_id, RuleTriggerLog.project_id)
Index("idx_metric_company_project", MetricCatalog.company_id, MetricCatalog.project_id)
Index("idx_agent_dag_run_company_project", AgentDagRun.company_id, AgentDagRun.project_id)
Index("idx_agent_dag_run_user_created", AgentDagRun.user_id, AgentDagRun.created_at)
Index("idx_agent_dag_step_run_run", AgentDagStepRun.run_id)
Index("idx_agent_approval_company_project", AgentApprovalRequest.company_id, AgentApprovalRequest.project_id)
Index("idx_agent_approval_status_created", AgentApprovalRequest.status, AgentApprovalRequest.created_at)
Index("idx_agent_approval_run_step", AgentApprovalRequest.run_id, AgentApprovalRequest.step_run_id)
Index("idx_worker_project_date", WorkerRiskProfile.worker_id, WorkerRiskProfile.project_id, WorkerRiskProfile.calc_date, unique=True)
Index("idx_sub_project_date", SubcontractorRiskProfile.subcontractor_id, SubcontractorRiskProfile.project_id, SubcontractorRiskProfile.calc_date, unique=True)
Index("idx_agent_session_scope", AgentSessionSummary.tenant_id, AgentSessionSummary.user_id, AgentSessionSummary.session_id, unique=True)
Index("idx_agent_prompt_active", AgentPromptVersion.agent_code, AgentPromptVersion.is_active)
Index("idx_agent_feedback_task", AgentFeedback.task_id)
Index("idx_agent_feedback_agent_time", AgentFeedback.agent_name, AgentFeedback.created_at)
Index("idx_agent_feedback_company_project", AgentFeedback.company_id, AgentFeedback.project_id)
Index("idx_webhook_delivery_company_project", WebhookDeliveryLog.company_id, WebhookDeliveryLog.project_id)
Index("idx_webhook_delivery_status_time", WebhookDeliveryLog.delivery_status, WebhookDeliveryLog.created_at)
Index("idx_webhook_delivery_event_time", WebhookDeliveryLog.event_type, WebhookDeliveryLog.created_at)
Index("idx_user_account_company_user", UserAccount.company_id, UserAccount.user_id)
Index("idx_user_role_company_user", UserRole.company_id, UserRole.user_id)
Index("idx_user_role_project", UserRole.project_id, UserRole.role_code)
