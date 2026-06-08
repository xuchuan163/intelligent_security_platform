import datetime as dt
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.infrastructure.database.models import Hazard, Project, ProjectUser, SafetyWorkOrder, WorkOrderFlowLog
from app.infrastructure.database.session import Base, get_db
from app.main import app


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    _seed_base(db)
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))

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


def _seed_base(db) -> None:
    db.add(
        Project(
            project_id="P002",
            tenant_id="COMPANY-A",
            company_id="COMPANY-A",
            org_path="COMPANY-A/P002",
            project_name="Wuhan Center",
            status="active",
        )
    )
    db.add_all(
        [
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-GC-01",
                user_name="GC Safety",
                role_code="gc_safety_officer",
            ),
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-DIR-01",
                user_name="Safety Director",
                role_code="safety_director",
            ),
            ProjectUser(
                tenant_id="COMPANY-A",
                company_id="COMPANY-A",
                org_path="COMPANY-A/P002",
                project_id="P002",
                user_id="U-SUB-S003",
                user_name="Sub Safety",
                role_code="sub_safety_officer",
                subcontractor_id="S003",
            ),
        ]
    )
    db.commit()


def _gc_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": "COMPANY-A",
        "X-Company-Id": "COMPANY-A",
        "X-Mock-User-Id": "U-GC-01",
        "X-Role": "gc_safety_officer",
        "X-Scope-Type": "project",
        "X-Authorized-Project-Ids": "P002",
    }


def _director_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": "COMPANY-A",
        "X-Company-Id": "COMPANY-A",
        "X-Mock-User-Id": "U-DIR-01",
        "X-Role": "safety_director",
        "X-Scope-Type": "project",
        "X-Authorized-Project-Ids": "P002",
    }


def _sub_headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": "COMPANY-A",
        "X-Company-Id": "COMPANY-A",
        "X-Mock-User-Id": "U-SUB-S003",
        "X-Role": "sub_safety_officer",
        "X-Subcontractor-Id": "S003",
        "X-Scope-Type": "project",
        "X-Authorized-Project-Ids": "P002",
    }


def test_upload_hazard_multipart_creates_hazard_order_flow_and_file(api_client):
    client, db = api_client

    response = client.post(
        "/api/v1/projects/P002/hazards",
        data={
            "description": "Missing edge protection near foundation pit with fall risk.",
            "hazard_type": "edge_protection",
            "hazard_level": "major",
            "subcontractor_id": "S003",
            "due_date": "2026-06-12",
            "location": "foundation pit east",
        },
        files={"images": ("hazard.png", b"fake-png-content", "image/png")},
        headers=_gc_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "SUCCESS"
    assert body["data"]["work_order_status"] == "pending_confirm"

    hazard = db.query(Hazard).one()
    order = db.query(SafetyWorkOrder).one()
    create_log = db.query(WorkOrderFlowLog).one()

    assert hazard.work_order_id == order.work_order_id
    assert hazard.attachments["items"][0]["phase"] == "discovery"
    assert order.status == "pending_confirm"
    assert create_log.action == "create"
    assert Path(settings.upload_dir, "COMPANY-A", "P002").exists()


def test_patch_work_order_status_uses_workflow_service_for_confirm(api_client):
    client, db = api_client
    order = SafetyWorkOrder(
        work_order_id="WO-API-001",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        work_order_type="hazard_rectification",
        project_id="P002",
        subcontractor_id="S003",
        status="pending_confirm",
    )
    db.add(order)
    db.commit()

    response = client.patch(
        "/api/v1/work-orders/WO-API-001/status",
        json={
            "action": "confirm",
            "assignee_user_id": "U-SUB-S003",
            "due_time": "2026-06-10T18:00:00",
            "comment": "Dispatch to subcontractor.",
        },
        headers=_director_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["new_status"] == "dispatched"

    db.refresh(order)
    assert order.status == "dispatched"
    assert order.responsible_user_id == "U-SUB-S003"
    assert db.query(WorkOrderFlowLog).filter_by(work_order_id="WO-API-001", action="confirm").count() == 1


def test_get_file_returns_scoped_local_upload(api_client):
    client, _db = api_client
    upload_response = client.post(
        "/api/v1/projects/P002/hazards",
        data={
            "description": "Missing guardrail at stair opening with clear fall risk.",
            "hazard_type": "guardrail",
            "hazard_level": "general",
            "subcontractor_id": "S003",
            "due_date": "2026-06-12",
        },
        files={"images": ("hazard.jpg", b"image-body", "image/jpeg")},
        headers=_gc_headers(),
    )
    assert upload_response.status_code == 200
    file_id = upload_response.json()["data"]["attachments"][0]["file_id"]

    response = client.get(f"/api/v1/files/{file_id}", headers=_gc_headers())

    assert response.status_code == 200
    assert response.content == b"image-body"
    assert response.headers["content-type"].startswith("image/jpeg")


def test_patch_work_order_status_accepts_multipart_rectification_image(api_client):
    client, db = api_client
    order = SafetyWorkOrder(
        work_order_id="WO-API-002",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        work_order_type="hazard_rectification",
        project_id="P002",
        subcontractor_id="S003",
        status="processing",
    )
    db.add(order)
    db.commit()

    response = client.patch(
        "/api/v1/work-orders/WO-API-002/status",
        data={"action": "submit_result", "comment": "Rectification completed."},
        files={"images": ("fixed.jpg", b"fixed-image-body", "image/jpeg")},
        headers=_sub_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["new_status"] == "waiting_review"

    db.refresh(order)
    flow = db.query(WorkOrderFlowLog).filter_by(work_order_id="WO-API-002", action="submit_result").one()
    attachment = order.attachments["items"][0]
    assert order.status == "waiting_review"
    assert attachment["phase"] == "rectification"
    assert flow.attachments["items"][0]["file_id"] == attachment["file_id"]


def test_get_work_order_detail_returns_attachments_and_flow_logs(api_client):
    client, db = api_client
    order = SafetyWorkOrder(
        work_order_id="WO-API-DETAIL",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        work_order_type="hazard_rectification",
        project_id="P002",
        subcontractor_id="S003",
        status="dispatched",
        attachments={"items": [{"file_id": "F-DETAIL", "phase": "discovery"}]},
    )
    flow = WorkOrderFlowLog(
        work_order_id="WO-API-DETAIL",
        from_status="pending_confirm",
        to_status="dispatched",
        action="confirm",
        operator_user_id="U-DIR-01",
        operator_role="safety_director",
        comment="Dispatched.",
    )
    db.add_all([order, flow])
    db.commit()

    response = client.get("/api/v1/work-orders/WO-API-DETAIL", headers=_gc_headers())

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["work_order_id"] == "WO-API-DETAIL"
    assert data["attachments"]["items"][0]["file_id"] == "F-DETAIL"
    assert data["flow_logs"][0]["action"] == "confirm"
    assert data["flow_logs"][0]["to_status"] == "dispatched"
