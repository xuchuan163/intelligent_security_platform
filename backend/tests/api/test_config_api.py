from fastapi.testclient import TestClient

from app.main import app


def _headers() -> dict[str, str]:
    return {
        "X-Mock-User-Id": "mock-admin",
        "X-Tenant-Id": "CSCEC",
        "X-Role": "platform_admin",
    }


def test_weight_versions_route_returns_registered_configs():
    client = TestClient(app)

    response = client.get("/api/v1/config/weight-versions", headers=_headers())

    assert response.status_code == 200
    body = response.json()
    assert body["code"] == "SUCCESS"
    items = body["data"]["items"]
    assert len(items) == 2
    assert {item["config_key"] for item in items} == {"project_type_matrix", "dynamic_factors"}


def test_weight_versions_route_requires_profile_read_permission():
    client = TestClient(app)

    response = client.get(
        "/api/v1/config/weight-versions",
        headers={
            "X-Mock-User-Id": "guest-user",
            "X-Tenant-Id": "CSCEC",
            "X-Role": "guest",
        },
    )

    assert response.status_code == 403
