import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser
from app.infrastructure.database.models import (
    Project,
    ProjectRiskProfile,
    RuleTriggerLog,
    SafetyWorkOrder,
    Subcontractor,
    SubcontractorRiskProfile,
    Worker,
    WorkerRiskProfile,
)
from app.infrastructure.database.session import Base
from app.schemas.work_orders import WorkOrderCreate
from app.services.dashboard.service import get_dashboard_overview
from app.services.profiles.service import (
    get_project_profile,
    get_project_ranking,
    get_subcontractor_profile,
    get_worker_profile,
)
from app.services.rules.service import list_rule_triggers
from app.services.work_orders.service import create_work_order, list_work_orders


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _org_user() -> MockUser:
    return MockUser(
        user_id="u-safety-001",
        user_name="Safety Manager",
        tenant_id="TENANT-A",
        org_path="TENANT-A/BU-01",
        role="safety_manager",
        data_scope=DataScope.ORG,
    )


def _tenant_user() -> MockUser:
    return MockUser(
        user_id="u-platform-001",
        user_name="Platform Admin",
        tenant_id="TENANT-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
    )


def test_work_order_list_filters_by_tenant_and_org_scope():
    db = _session()
    db.add_all(
        [
            Project(
                project_id="P-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                project_name="范围内项目",
            ),
            Project(
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                project_name="范围外项目",
            ),
            Project(
                project_id="P-OTHER",
                tenant_id="TENANT-B",
                org_path="TENANT-B/BU-01/PROJECT-03",
                project_name="其他租户项目",
            ),
            SafetyWorkOrder(
                work_order_id="WO-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                work_order_type="hazard_rectification",
                project_id="P-IN",
                title="范围内工单",
                status="pending_confirm",
                priority="normal",
                created_at=dt.datetime(2026, 1, 1, 9, 0, 0),
            ),
            SafetyWorkOrder(
                work_order_id="WO-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                work_order_type="hazard_rectification",
                project_id="P-OUT",
                title="范围外工单",
                status="pending_confirm",
                priority="normal",
                created_at=dt.datetime(2026, 1, 2, 9, 0, 0),
            ),
            SafetyWorkOrder(
                work_order_id="WO-OTHER",
                tenant_id="TENANT-B",
                org_path="TENANT-B/BU-01/PROJECT-03",
                work_order_type="hazard_rectification",
                project_id="P-OTHER",
                title="其他租户工单",
                status="pending_confirm",
                priority="normal",
                created_at=dt.datetime(2026, 1, 3, 9, 0, 0),
            ),
        ]
    )
    db.commit()

    user = MockUser(
        user_id="u-safety-001",
        user_name="安全主管",
        tenant_id="TENANT-A",
        org_path="TENANT-A/BU-01",
        role="safety_manager",
        data_scope=DataScope.ORG,
    )

    rows = list_work_orders(db, current_user=user)

    assert [row["work_order_id"] for row in rows] == ["WO-IN"]


def test_create_work_order_rejects_project_outside_user_scope():
    db = _session()
    db.add(
        Project(
            project_id="P-OUT",
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-02/PROJECT-02",
            project_name="范围外项目",
        )
    )
    db.commit()
    user = MockUser(
        user_id="u-safety-001",
        user_name="Safety Manager",
        tenant_id="TENANT-A",
        org_path="TENANT-A/BU-01",
        role="safety_manager",
        data_scope=DataScope.ORG,
    )

    try:
        create_work_order(
            db,
            WorkOrderCreate(
                work_order_type="hazard_rectification",
                title="越权创建工单",
                project_id="P-OUT",
            ),
            current_user=user,
        )
    except PermissionError as exc:
        assert "outside current user data scope" in str(exc)
    else:
        raise AssertionError("Expected PermissionError for out-of-scope project")


def test_project_profile_detail_hides_profiles_outside_org_scope():
    db = _session()
    today = dt.date.today()
    db.add_all(
        [
            Project(
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                project_name="Out Project",
            ),
            ProjectRiskProfile(
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                calc_date=today,
                total_risk_score=88,
                risk_level="critical",
            ),
        ]
    )
    db.commit()

    assert get_project_profile(db, "P-OUT", current_user=_org_user()) is None


def test_worker_profile_detail_hides_profiles_outside_org_scope():
    db = _session()
    today = dt.date.today()
    db.add_all(
        [
            Worker(
                worker_id="W-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                project_id="P-OUT",
                worker_name_masked="W**",
            ),
            WorkerRiskProfile(
                worker_id="W-OUT",
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                calc_date=today,
                total_risk_score=77,
                risk_level="high",
            ),
        ]
    )
    db.commit()

    assert get_worker_profile(db, "W-OUT", current_user=_org_user()) is None


def test_subcontractor_profile_detail_hides_profiles_outside_org_scope():
    db = _session()
    today = dt.date.today()
    db.add_all(
        [
            Subcontractor(
                subcontractor_id="S-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                subcontractor_name="Out Sub",
            ),
            SubcontractorRiskProfile(
                subcontractor_id="S-OUT",
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                calc_date=today,
                total_risk_score=69,
                risk_level="high",
            ),
        ]
    )
    db.commit()

    assert get_subcontractor_profile(db, "S-OUT", current_user=_org_user()) is None


def test_project_ranking_filters_by_org_scope():
    db = _session()
    today = dt.date.today()
    db.add_all(
        [
            Project(
                project_id="P-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                project_name="In Project",
            ),
            Project(
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                project_name="Out Project",
            ),
            ProjectRiskProfile(
                project_id="P-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                calc_date=today,
                total_risk_score=55,
                risk_level="medium",
            ),
            ProjectRiskProfile(
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                calc_date=today,
                total_risk_score=99,
                risk_level="critical",
            ),
        ]
    )
    db.commit()

    rows = get_project_ranking(db, current_user=_org_user())

    assert [row["project_id"] for row in rows] == ["P-IN"]


def test_dashboard_overview_filters_counts_and_rankings_by_org_scope():
    db = _session()
    today = dt.date.today()
    db.add_all(
        [
            Project(
                project_id="P-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                project_name="In Project",
            ),
            Project(
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                project_name="Out Project",
            ),
            ProjectRiskProfile(
                project_id="P-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                calc_date=today,
                total_risk_score=66,
                risk_level="high",
            ),
            ProjectRiskProfile(
                project_id="P-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                calc_date=today,
                total_risk_score=99,
                risk_level="critical",
            ),
            SafetyWorkOrder(
                work_order_id="WO-IN",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                work_order_type="hazard_rectification",
                status="processing",
            ),
            SafetyWorkOrder(
                work_order_id="WO-OUT",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                work_order_type="hazard_rectification",
                status="processing",
            ),
        ]
    )
    db.commit()

    data = get_dashboard_overview(db, current_user=_org_user())

    assert data["total_projects"] == 1
    assert data["high_risk_projects"] == 1
    assert data["critical_risk_projects"] == 0
    assert data["open_work_orders"] == 1
    assert [row["project_id"] for row in data["project_ranking"]] == ["P-IN"]


def test_dashboard_recent_rule_triggers_filters_by_tenant_scope():
    db = _session()
    now = dt.datetime.utcnow()
    db.add_all(
        [
            RuleTriggerLog(
                rule_id="SR-PROJ-001",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                object_type="project",
                object_id="P-IN",
                project_id="P-IN",
                trigger_condition="major overdue",
                severity="critical",
                created_at=now,
            ),
            RuleTriggerLog(
                rule_id="SR-PROJ-001",
                tenant_id="TENANT-B",
                org_path="TENANT-B/BU-01/PROJECT-01",
                object_type="project",
                object_id="P-OTHER",
                project_id="P-OTHER",
                trigger_condition="major overdue",
                severity="critical",
                created_at=now + dt.timedelta(seconds=1),
            ),
        ]
    )
    db.commit()

    data = get_dashboard_overview(db, current_user=_tenant_user())

    assert [row["project_id"] for row in data["recent_rule_triggers"]] == ["P-IN"]


def test_rule_trigger_list_filters_by_org_scope():
    db = _session()
    now = dt.datetime.utcnow()
    db.add_all(
        [
            RuleTriggerLog(
                rule_id="SR-PROJ-001",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-01/PROJECT-01",
                object_type="project",
                object_id="P-IN",
                project_id="P-IN",
                trigger_condition="major overdue",
                severity="critical",
                created_at=now,
            ),
            RuleTriggerLog(
                rule_id="SR-PROJ-004",
                tenant_id="TENANT-A",
                org_path="TENANT-A/BU-02/PROJECT-02",
                object_type="project",
                object_id="P-OUT",
                project_id="P-OUT",
                trigger_condition="equipment overdue",
                severity="high",
                created_at=now + dt.timedelta(seconds=1),
            ),
        ]
    )
    db.commit()

    rows = list_rule_triggers(db, current_user=_org_user())

    assert [row["project_id"] for row in rows] == ["P-IN"]
