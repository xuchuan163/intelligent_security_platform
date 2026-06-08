"""HTTP API load-test helpers for performance benchmarks (Phase 4-C.2)."""

from __future__ import annotations

import datetime as dt
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Literal

RequestFn = Callable[[str, str], "RequestResult"]

HttpMethod = Literal["GET", "POST"]


@dataclass(frozen=True)
class LoadTestEndpoint:
    name: str
    method: HttpMethod
    path: str
    sla_p95_ms: float | None = None


@dataclass(frozen=True)
class RequestResult:
    status_code: int
    elapsed_ms: float
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status_code < 300


@dataclass(frozen=True)
class LoadTestConfig:
    base_url: str = "http://127.0.0.1:8000"
    tenant_id: str = "CSCEC-SCALE"
    iterations: int = 30
    concurrency: int = 4
    timeout_seconds: float = 30.0


DEFAULT_ENDPOINTS: tuple[LoadTestEndpoint, ...] = (
    LoadTestEndpoint("dashboard_overview", "GET", "/api/v1/dashboard/overview", sla_p95_ms=800),
    LoadTestEndpoint("projects_list", "GET", "/api/v1/projects", sla_p95_ms=500),
    LoadTestEndpoint("profile_ranking", "GET", "/api/v1/profile/ranking/projects", sla_p95_ms=500),
    LoadTestEndpoint("work_orders_list", "GET", "/api/v1/work-orders", sla_p95_ms=500),
)


def build_load_test_headers(
    *,
    tenant_id: str,
    user_id: str = "scale-load-test",
    role: str = "platform_admin",
) -> dict[str, str]:
    return {
        "X-Mock-User-Id": user_id,
        "X-Mock-User-Name": "Scale Load Test",
        "X-Tenant-Id": tenant_id,
        "X-Org-Path": tenant_id,
        "X-Role": role,
        "X-Data-Scope": "tenant",
        "X-Company-Id": tenant_id,
    }


def _percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * ratio))))
    return round(ordered[index], 2)


def _latency_stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"min": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0, "p99": 0.0, "max": 0.0}
    return {
        "min": round(min(values), 2),
        "avg": round(sum(values) / len(values), 2),
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "p99": _percentile(values, 0.99),
        "max": round(max(values), 2),
    }


def _run_endpoint_batch(
    request_fn: RequestFn,
    endpoint: LoadTestEndpoint,
    *,
    iterations: int,
    concurrency: int,
) -> list[RequestResult]:
    if concurrency <= 1:
        return [request_fn(endpoint.method, endpoint.path) for _ in range(iterations)]

    results: list[RequestResult] = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(request_fn, endpoint.method, endpoint.path)
            for _ in range(iterations)
        ]
        for future in as_completed(futures):
            results.append(future.result())
    return results


def run_api_load_test(
    request_fn: RequestFn,
    *,
    config: LoadTestConfig | None = None,
    endpoints: tuple[LoadTestEndpoint, ...] | None = None,
) -> dict[str, Any]:
    config = config or LoadTestConfig()
    endpoints = endpoints or DEFAULT_ENDPOINTS
    if config.iterations < 1:
        raise ValueError("iterations must be >= 1")
    if config.concurrency < 1:
        raise ValueError("concurrency must be >= 1")

    endpoint_reports: list[dict[str, Any]] = []
    total_requests = 0
    total_errors = 0
    sla_failures: list[str] = []

    for endpoint in endpoints:
        results = _run_endpoint_batch(
            request_fn,
            endpoint,
            iterations=config.iterations,
            concurrency=config.concurrency,
        )
        latencies = [item.elapsed_ms for item in results]
        errors = sum(1 for item in results if not item.ok)
        total_requests += len(results)
        total_errors += errors

        latency = _latency_stats(latencies)
        sla_passed = True
        if endpoint.sla_p95_ms is not None and latency["p95"] > endpoint.sla_p95_ms:
            sla_passed = False
            sla_failures.append(
                f"{endpoint.name}: p95={latency['p95']}ms > sla={endpoint.sla_p95_ms}ms"
            )

        endpoint_reports.append(
            {
                "name": endpoint.name,
                "method": endpoint.method,
                "path": endpoint.path,
                "count": len(results),
                "errors": errors,
                "error_rate": round(errors / len(results), 4) if results else 0.0,
                "latency_ms": latency,
                "sla_p95_ms": endpoint.sla_p95_ms,
                "sla_passed": sla_passed,
            }
        )

    error_rate = round(total_errors / total_requests, 4) if total_requests else 0.0
    return {
        "meta": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "base_url": config.base_url,
            "tenant_id": config.tenant_id,
            "iterations": config.iterations,
            "concurrency": config.concurrency,
            "timeout_seconds": config.timeout_seconds,
        },
        "summary": {
            "total_requests": total_requests,
            "total_errors": total_errors,
            "error_rate": error_rate,
            "sla_passed": not sla_failures,
            "sla_failures": sla_failures,
        },
        "endpoints": endpoint_reports,
    }


def build_httpx_request_fn(
    *,
    base_url: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> RequestFn:
    import httpx

    client = httpx.Client(base_url=base_url, headers=headers, timeout=timeout_seconds)

    def _request(method: str, path: str) -> RequestResult:
        started = time.perf_counter()
        try:
            response = client.request(method, path)
            elapsed_ms = (time.perf_counter() - started) * 1000
            return RequestResult(status_code=response.status_code, elapsed_ms=elapsed_ms)
        except httpx.HTTPError as exc:
            elapsed_ms = (time.perf_counter() - started) * 1000
            return RequestResult(status_code=0, elapsed_ms=elapsed_ms, error=str(exc))

    return _request


def build_test_client_request_fn(client: Any) -> RequestFn:
    def _request(method: str, path: str) -> RequestResult:
        started = time.perf_counter()
        try:
            response = client.request(method, path)
            elapsed_ms = (time.perf_counter() - started) * 1000
            return RequestResult(status_code=response.status_code, elapsed_ms=elapsed_ms)
        except Exception as exc:  # pragma: no cover - defensive for test harness
            elapsed_ms = (time.perf_counter() - started) * 1000
            return RequestResult(status_code=0, elapsed_ms=elapsed_ms, error=str(exc))

    return _request
