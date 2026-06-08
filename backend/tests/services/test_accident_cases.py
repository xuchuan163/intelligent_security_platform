import datetime as dt

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import DataScope, MockUser
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base, get_db
from app.main import app
from scripts.seed_demo_data import seed_accident_cases
from app.services.cases.service import list_accident_cases


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _user(tenant_id: str = "TENANT-A") -> MockUser:
    return MockUser(
        user_id="u-safety-001",
        user_name="Safety Manager",
        tenant_id=tenant_id,
        org_path=tenant_id,
        role="safety_manager",
        data_scope=DataScope.TENANT,
    )


def _seed_cases(db, tenant_id: str = "TENANT-A", count: int = 5) -> None:
    for idx in range(1, count + 1):
        db.add(
            AccidentCaseLibrary(
                accident_case_id=f"CASE-{tenant_id}-{idx:03d}",
                tenant_id=tenant_id,
                accident_type=["高处坠落", "物体打击", "触电", "机械伤害", "坍塌"][idx - 1],
                severity="一般事故",
                project_type="housing",
                operation_scene="主体结构施工",
                direct_cause="现场防护措施不到位",
                indirect_cause="班前教育和旁站监督不足",
                involved_subjects={"project": "demo", "subjects": ["subcontractor", "worker"]},
                warning_indicators=[{"metric_code": "HAZARD_OVERDUE_COUNT", "value": idx}],
                rectification_measures="补齐防护、复核交底、闭环整改",
                tags=["事故案例", "MVP"],
                status="active",
                created_at=dt.datetime(2026, 6, idx, 9, 0, 0),
            )
        )
    db.commit()


def test_list_accident_cases_returns_seeded_cases_for_current_tenant():
    db = _session()
    _seed_cases(db, tenant_id="TENANT-A", count=5)

    data = list_accident_cases(db, current_user=_user("TENANT-A"), page_size=10)

    assert data["total"] == 5
    assert len(data["items"]) == 5
    assert {item["tenant_id"] for item in data["items"]} == {"TENANT-A"}
    assert data["items"][0]["accident_case_id"] == "CASE-TENANT-A-005"


def test_list_accident_cases_filters_by_tenant():
    db = _session()
    _seed_cases(db, tenant_id="TENANT-A", count=2)
    _seed_cases(db, tenant_id="TENANT-B", count=2)

    data = list_accident_cases(db, current_user=_user("TENANT-A"), page_size=10)

    assert data["total"] == 2
    assert {item["tenant_id"] for item in data["items"]} == {"TENANT-A"}


def test_case_list_api_returns_success_envelope_with_cases():
    db = _session()
    _seed_cases(db, tenant_id="TENANT-A", count=5)

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    try:
        response = TestClient(app).get(
            "/api/v1/case/list",
            headers={"X-Tenant-Id": "TENANT-A", "X-Data-Scope": "tenant"},
        )
    finally:
        app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["code"] == "SUCCESS"
    assert body["data"]["total"] == 5
    assert len(body["data"]["items"]) == 5


def test_seed_accident_cases_upserts_at_least_fifty_demo_cases():
    from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS, CORE_ACCIDENT_TYPES

    db = _session()

    seed_accident_cases(db)
    seed_accident_cases(db)

    assert len(ACCIDENT_CASE_SEEDS) >= 50
    seeded_types = {item["accident_type"] for item in ACCIDENT_CASE_SEEDS}
    assert set(CORE_ACCIDENT_TYPES) <= seeded_types

    data = list_accident_cases(db, current_user=_user("CSCEC"), page_size=60)
    assert data["total"] >= 50
    assert len(data["items"]) >= 50
    assert data["items"][0]["accident_case_id"].startswith("AC-MVP-")
    assert {item["tenant_id"] for item in data["items"]} == {"CSCEC"}


def test_seed_accident_cases_cover_four_project_types():
    from app.services.cases.seed_cases import ACCIDENT_CASE_SEEDS

    project_types = {item["project_type"] for item in ACCIDENT_CASE_SEEDS}
    assert project_types >= {"housing", "municipal", "infrastructure", "mep"}
