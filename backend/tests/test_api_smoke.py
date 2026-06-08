import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

ROOT_MAIN = Path(__file__).resolve().parents[2] / "main.py"
spec = importlib.util.spec_from_file_location("root_launcher", ROOT_MAIN)
assert spec is not None and spec.loader is not None
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


def test_projects_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/projects")

    assert response.status_code in {200, 503}
    if response.status_code == 200:
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert "items" in body["data"]


def test_dashboard_overview_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/dashboard/overview")

    assert response.status_code in {200, 503}


def test_work_orders_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/work-orders")

    assert response.status_code in {200, 503}


def test_work_order_overdue_escalation_route_exists():
    client = TestClient(app)

    response = client.post("/api/v1/work-orders/escalate-overdue")

    assert response.status_code in {200, 503}


def test_agent_feedback_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/agent/feedback")

    assert response.status_code in {200, 503}


def test_project_weekly_report_route_is_mounted():
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert any("project-weekly" in path for path in route_paths)


def test_subcontractor_eval_report_route_is_mounted():
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert any("subcontractor-eval" in path for path in route_paths)


def test_webhook_test_route_is_mounted():
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert any("/webhooks/test" in path for path in route_paths)


def test_graph_neighbors_route_is_mounted():
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert any("/graph/neighbors" in path for path in route_paths)


def test_webhook_dispatch_routes_are_mounted():
    route_paths = {getattr(route, "path", "") for route in app.routes}
    assert any("/webhooks/dispatch/rule-trigger" in path for path in route_paths)
    assert any("/webhooks/dispatch/work-order-overdue" in path for path in route_paths)


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


def test_validation_error_uses_unified_error_envelope():
    client = TestClient(app)

    response = client.post(
        "/api/v1/work-orders",
        json={"project_id": "P001"},
        headers={"X-Request-Id": "REQ-VALIDATION-001"},
    )

    body = response.json()
    assert response.status_code == 422
    assert response.headers["X-Request-Id"] == "REQ-VALIDATION-001"
    assert body["code"] == "42201"
    assert body["request_id"] == "REQ-VALIDATION-001"
    assert body["data"]["errors"]
    assert "timestamp" in body


def test_not_found_error_uses_unified_error_envelope():
    client = TestClient(app)

    response = client.get("/api/v1/not-exists", headers={"X-Request-Id": "REQ-404-001"})

    body = response.json()
    assert response.status_code == 404
    assert response.headers["X-Request-Id"] == "REQ-404-001"
    assert body == {
        "code": "40401",
        "message": "Not Found",
        "request_id": "REQ-404-001",
        "data": None,
        "timestamp": body["timestamp"],
    }


def test_project_risk_explanation_requires_project_id():
    client = TestClient(app)

    response = client.post("/api/v1/assistant/project-risk-explanation", json={"facts": {}})

    assert response.status_code == 422


def test_metrics_catalog_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/metrics/catalog")

    assert response.status_code in {200, 503}
    if response.status_code == 200:
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert {"page_no", "page_size", "total", "items"} <= set(body["data"])


def test_case_list_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/case/list")

    assert response.status_code in {200, 503}
    if response.status_code == 200:
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert {"page_no", "page_size", "total", "items"} <= set(body["data"])


def test_metric_detail_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/metrics/PROJECT_RISK_SCORE")

    assert response.status_code in {200, 404, 503}
    if response.status_code == 200:
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert body["data"]["metric_code"] == "PROJECT_RISK_SCORE"


def test_backend_default_database_targets_intelligent_security_platform():
    assert "intelligent_security_platform" in settings.database_url


def test_launcher_defaults_to_local_platform_database_without_reset():
    assert launcher.MYSQL_DATABASE == "intelligent_security_platform"
    assert launcher.RESET_DATABASE_ON_START is False
