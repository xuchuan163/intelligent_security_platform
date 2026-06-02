from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_overview_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/dashboard/overview")

    assert response.status_code in {200, 503}


def test_work_orders_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/work-orders")

    assert response.status_code in {200, 503}


def test_rules_triggers_route_is_mounted():
    client = TestClient(app)

    response = client.get("/api/v1/rules/triggers")

    assert response.status_code in {200, 503}


def test_profile_recalculate_route_exists():
    client = TestClient(app)

    response = client.post("/api/v1/profile/recalculate")

    assert response.status_code in {200, 503}
    if response.status_code == 200:
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert "recalculated_projects" in body["data"]


def test_create_work_order_rejects_missing_required_fields():
    client = TestClient(app)

    response = client.post("/api/v1/work-orders", json={"project_id": "P001"})

    assert response.status_code == 422


def test_project_risk_explanation_requires_project_id():
    client = TestClient(app)

    response = client.post("/api/v1/assistant/project-risk-explanation", json={"facts": {}})

    assert response.status_code == 422
