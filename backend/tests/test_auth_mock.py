from fastapi.testclient import TestClient

from app.main import app


def test_auth_me_returns_mock_user_context_from_headers():
    client = TestClient(app)

    response = client.get(
        "/api/v1/auth/me",
        headers={
            "X-Mock-User-Id": "u-safety-001",
            "X-Mock-User-Name": "Safety Manager",
            "X-Tenant-Id": "TENANT-A",
            "X-Org-Path": "TENANT-A/BU-01/PROJECT-01",
            "X-Role": "safety_manager",
            "X-Data-Scope": "org",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "SUCCESS"
    assert body["data"] | {
        "user_id": "u-safety-001",
        "user_name": "Safety Manager",
        "tenant_id": "TENANT-A",
        "org_path": "TENANT-A/BU-01/PROJECT-01",
        "role": "safety_manager",
        "data_scope": "org",
    } == body["data"]
    assert body["data"]["company_id"] == "TENANT-A"
    assert body["data"]["scope_type"] == "project"
    assert body["data"]["authorized_project_ids"] == []
