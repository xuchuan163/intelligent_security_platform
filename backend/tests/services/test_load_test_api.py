"""API load-test helper tests (Phase 4-C.2)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.session import Base, get_db
from app.main import app
from app.services.scale.load_test_api import (
    DEFAULT_ENDPOINTS,
    LoadTestConfig,
    LoadTestEndpoint,
    RequestResult,
    build_load_test_headers,
    build_test_client_request_fn,
    run_api_load_test,
)
from app.services.scale.seed_scale_data import ScaleSeedConfig, seed_scale_data


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_run_api_load_test_computes_percentiles():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    state = {"index": 0}

    def request_fn(_method: str, _path: str) -> RequestResult:
        elapsed = latencies[state["index"] % len(latencies)]
        state["index"] += 1
        return RequestResult(status_code=200, elapsed_ms=elapsed)

    report = run_api_load_test(
        request_fn,
        config=LoadTestConfig(iterations=10, concurrency=1),
        endpoints=(LoadTestEndpoint("sample", "GET", "/api/v1/sample", sla_p95_ms=95),),
    )

    endpoint = report["endpoints"][0]
    assert endpoint["count"] == 10
    assert endpoint["errors"] == 0
    assert endpoint["latency_ms"]["p50"] == 50.0
    assert endpoint["latency_ms"]["p95"] == 100.0
    assert endpoint["sla_passed"] is False
    assert report["summary"]["sla_passed"] is False


def test_run_api_load_test_with_test_client_and_scale_seed():
    db = _session()
    seed_scale_data(
        db,
        ScaleSeedConfig(
            tenant_id="TENANT-LOAD",
            project_count=10,
            subcontractors_per_project=1,
            workers_per_project=2,
            with_profiles=True,
        ),
    )

    def override_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)
    for header, value in build_load_test_headers(tenant_id="TENANT-LOAD").items():
        client.headers[header] = value

    try:
        report = run_api_load_test(
            build_test_client_request_fn(client),
            config=LoadTestConfig(
                base_url="testclient",
                tenant_id="TENANT-LOAD",
                iterations=5,
                concurrency=1,
            ),
            endpoints=DEFAULT_ENDPOINTS,
        )
    finally:
        app.dependency_overrides.clear()

    assert report["summary"]["total_requests"] == 5 * len(DEFAULT_ENDPOINTS)
    assert report["summary"]["error_rate"] == 0.0
    for endpoint in report["endpoints"]:
        assert endpoint["errors"] == 0
        assert endpoint["latency_ms"]["p95"] >= 0


def test_build_load_test_headers_contains_tenant_scope():
    headers = build_load_test_headers(tenant_id="CSCEC-SCALE")
    assert headers["X-Tenant-Id"] == "CSCEC-SCALE"
    assert headers["X-Company-Id"] == "CSCEC-SCALE"
    assert headers["X-Data-Scope"] == "tenant"
