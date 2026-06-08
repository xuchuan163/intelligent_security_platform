from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_success():
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["code"] == "SUCCESS"
    assert payload["message"] == "ok"
    assert payload["data"]["status"] in {"healthy", "degraded"}
    assert payload["data"]["redis"]["status"] in {"ready", "unavailable"}
    assert payload["data"]["milvus"]["status"] in {"disabled", "unavailable", "ready"}
