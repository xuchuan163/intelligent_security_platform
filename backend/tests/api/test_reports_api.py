import datetime as dt
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.models import (
    Project,
    ProjectRiskProfile,
    Subcontractor,
    SubcontractorRiskProfile,
)
from app.infrastructure.database.session import Base, get_db
from app.main import app

TODAY = dt.date(2026, 6, 3)


def _client_with_db() -> Iterator[tuple[TestClient, Session]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    db.add(
        Project(
            project_id="P001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P001",
            project_name="上海临港TOD综合开发项目",
            status="active",
        )
    )
    db.add(
        ProjectRiskProfile(
            project_id="P001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/EAST-REGION/P001",
            calc_date=TODAY,
            total_risk_score=55.0,
            risk_level="medium",
            data_completeness=0.85,
        )
    )
    db.add(
        Subcontractor(
            subcontractor_id="S001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P001/S001",
            subcontractor_name="华东建设劳务有限公司",
            status="active",
        )
    )
    db.add(
        SubcontractorRiskProfile(
            subcontractor_id="S001",
            project_id="P001",
            tenant_id="CSCEC",
            org_path="CSCEC/CSCEC-8B/P001/S001",
            calc_date=TODAY,
            total_risk_score=40.0,
            risk_level="medium",
            data_completeness=0.9,
        )
    )
    db.commit()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app), db
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()


def test_project_weekly_report_route(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "rbac_enforce", True)

    for client, _ in _client_with_db():
        denied = client.get(
            "/api/v1/reports/project-weekly/P001",
            headers={
                "X-Mock-User-Id": "viewer-no-dashboard",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "viewer",
            },
        )
        assert denied.status_code == 403

        response = client.get(
            "/api/v1/reports/project-weekly/P001",
            params={"week_end": TODAY.isoformat()},
            headers={
                "X-Mock-User-Id": "mock-admin",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "platform_admin",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SUCCESS"
        data = body["data"]
        assert data["project_id"] == "P001"
        assert "kpi" in data
        assert "rule_triggers" in data
        assert "work_orders" in data
        assert data["period"]["week_label"]

        missing = client.get(
            "/api/v1/reports/project-weekly/P404",
            headers={
                "X-Mock-User-Id": "mock-admin",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "platform_admin",
            },
        )
        assert missing.status_code == 404


def test_subcontractor_eval_report_route(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "mock")
    monkeypatch.setattr(settings, "rbac_enforce", True)

    for client, _ in _client_with_db():
        response = client.get(
            "/api/v1/reports/subcontractor-eval/S001",
            params={"project_id": "P001", "eval_date": TODAY.isoformat()},
            headers={
                "X-Mock-User-Id": "mock-admin",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "platform_admin",
            },
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SUCCESS"
        data = body["data"]
        assert data["subcontractor_id"] == "S001"
        assert data["profile"]["eval_grade"] == "合格"
        assert "kpi" in data
        assert "recommendations" in data

        missing = client.get(
            "/api/v1/reports/subcontractor-eval/S404",
            headers={
                "X-Mock-User-Id": "mock-admin",
                "X-Tenant-Id": "CSCEC",
                "X-Org-Path": "CSCEC",
                "X-Role": "platform_admin",
            },
        )
        assert missing.status_code == 404
