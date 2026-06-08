"""Profile recalculate batch timing benchmark (Phase 4-C.6)."""

from __future__ import annotations

import datetime as dt
import time
from dataclasses import dataclass
from typing import Any, Literal

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import DataScope, MockUser
from app.infrastructure.database.session import SessionLocal
from app.main import app
from app.schemas.profiles import ProfileRecalculateRequest
from app.services.profiles.service import recalculate_profiles
from app.services.scale.load_test_api import build_load_test_headers
from app.services.scale.seed_scale_data import ScaleSeedConfig, seed_scale_data

ProfileType = Literal["project", "worker", "subcontractor"]
BenchmarkMode = Literal["service", "api_testclient", "api_http"]

FULL_PROFILE_TYPES: tuple[ProfileType, ...] = ("project", "worker", "subcontractor")
DEFAULT_SCENARIOS: tuple[tuple[str, list[ProfileType]], ...] = (
    ("project_only", ["project"]),
    ("worker_only", ["worker"]),
    ("subcontractor_only", ["subcontractor"]),
    ("full_batch", list(FULL_PROFILE_TYPES)),
)


@dataclass(frozen=True)
class RecalculateBenchmarkConfig:
    tenant_id: str = "CSCEC-SCALE"
    projects: int = 500
    skip_seed: bool = False
    subcontractors_per_project: int = 2
    workers_per_project: int = 8
    seed_batch_size: int = 200
    id_prefix: str = "SCALE"
    sla_seconds: float = 30.0
    mode: BenchmarkMode = "api_testclient"
    base_url: str = "http://127.0.0.1:8000"
    timeout_seconds: float = 600.0


def build_benchmark_user(tenant_id: str) -> MockUser:
    return MockUser(
        user_id="scale-recalc-benchmark",
        user_name="Scale Recalculate Benchmark",
        tenant_id=tenant_id,
        org_path=tenant_id,
        role="platform_admin",
        data_scope=DataScope.TENANT,
        company_id=tenant_id,
    )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 2)


def _run_service_recalculate(
    db: Session,
    *,
    tenant_id: str,
    profile_types: list[ProfileType],
) -> tuple[dict[str, Any], float]:
    user = build_benchmark_user(tenant_id)
    request = ProfileRecalculateRequest(profile_types=profile_types)
    started = time.perf_counter()
    counts = recalculate_profiles(db, request, current_user=user)
    return counts, _elapsed_ms(started)


def _run_api_testclient_recalculate(
    *,
    tenant_id: str,
    profile_types: list[ProfileType],
) -> tuple[dict[str, Any], float, int | None]:
    client = TestClient(app)
    for header, value in build_load_test_headers(
        tenant_id=tenant_id,
        user_id="scale-recalc-benchmark",
        role="platform_admin",
    ).items():
        client.headers[header] = value

    started = time.perf_counter()
    response = client.post(
        "/api/v1/profile/recalculate",
        json={"profile_types": profile_types},
    )
    elapsed_ms = _elapsed_ms(started)
    if response.status_code != 200:
        return {"error": response.text}, elapsed_ms, response.status_code
    body = response.json()
    return body.get("data", {}), elapsed_ms, response.status_code


def _probe_http(base_url: str, tenant_id: str, timeout: float) -> bool:
    import httpx

    headers = build_load_test_headers(tenant_id=tenant_id, user_id="scale-recalc-benchmark")
    try:
        with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as client:
            response = client.get("/api/v1/dashboard/overview")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def _run_api_http_recalculate(
    *,
    base_url: str,
    tenant_id: str,
    profile_types: list[ProfileType],
    timeout_seconds: float,
) -> tuple[dict[str, Any], float, int | None]:
    import httpx

    headers = build_load_test_headers(tenant_id=tenant_id, user_id="scale-recalc-benchmark")
    started = time.perf_counter()
    with httpx.Client(base_url=base_url.rstrip("/"), headers=headers, timeout=timeout_seconds) as client:
        response = client.post(
            "/api/v1/profile/recalculate",
            json={"profile_types": profile_types},
        )
    elapsed_ms = _elapsed_ms(started)
    if response.status_code != 200:
        return {"error": response.text}, elapsed_ms, response.status_code
    body = response.json()
    return body.get("data", {}), elapsed_ms, response.status_code


def run_single_scenario(
    config: RecalculateBenchmarkConfig,
    *,
    scenario_name: str,
    profile_types: list[ProfileType],
    db: Session | None = None,
    resolved_mode: BenchmarkMode | None = None,
) -> dict[str, Any]:
    mode = resolved_mode or config.mode
    if mode == "service":
        if db is None:
            raise ValueError("db session is required for service mode")
        counts, elapsed_ms = _run_service_recalculate(db, tenant_id=config.tenant_id, profile_types=profile_types)
        status_code = 200
    elif mode == "api_http":
        counts, elapsed_ms, status_code = _run_api_http_recalculate(
            base_url=config.base_url,
            tenant_id=config.tenant_id,
            profile_types=profile_types,
            timeout_seconds=config.timeout_seconds,
        )
    else:
        counts, elapsed_ms, status_code = _run_api_testclient_recalculate(
            tenant_id=config.tenant_id,
            profile_types=profile_types,
        )

    sla_ms = config.sla_seconds * 1000
    error = counts.get("error")
    return {
        "name": scenario_name,
        "profile_types": profile_types,
        "elapsed_ms": elapsed_ms,
        "elapsed_seconds": round(elapsed_ms / 1000, 3),
        "sla_seconds": config.sla_seconds,
        "sla_passed": error is None and elapsed_ms <= sla_ms,
        "status_code": status_code,
        "counts": {key: value for key, value in counts.items() if key != "error"},
        "error": error,
    }


def resolve_benchmark_mode(config: RecalculateBenchmarkConfig) -> tuple[BenchmarkMode, list[str]]:
    notes: list[str] = []
    if config.mode == "api_http" or (config.mode == "api_testclient" and _probe_http(config.base_url, config.tenant_id, 5.0)):
        if _probe_http(config.base_url, config.tenant_id, 5.0):
            notes.append(f"压测通过 HTTP 访问运行中的 API（{config.base_url}）。")
            return "api_http", notes
    if config.mode == "api_http":
        notes.append(f"未检测到可访问的 API（{config.base_url}），回退为 TestClient 进程内压测。")
    else:
        notes.append(
            f"未检测到可访问的 API（{config.base_url}），回退为 TestClient 进程内压测；"
            "耗时仅供参考，生产级基线请在独立压测环境对 HTTP 服务复测。"
        )
    return "api_testclient", notes


def run_profile_recalculate_benchmark(config: RecalculateBenchmarkConfig) -> dict[str, Any]:
    seed_summary: dict[str, Any]
    if config.skip_seed:
        seed_summary = {
            "tenant_id": config.tenant_id,
            "totals": {"projects": config.projects},
            "skipped": True,
        }
    else:
        db = SessionLocal()
        try:
            result = seed_scale_data(
                db,
                ScaleSeedConfig(
                    tenant_id=config.tenant_id,
                    project_count=config.projects,
                    subcontractors_per_project=config.subcontractors_per_project,
                    workers_per_project=config.workers_per_project,
                    with_profiles=True,
                    batch_size=config.seed_batch_size,
                    id_prefix=config.id_prefix,
                ),
            )
            seed_summary = result.as_dict()
        finally:
            db.close()

    resolved_mode, notes = resolve_benchmark_mode(config)
    scenarios: list[dict[str, Any]] = []
    db_for_service: Session | None = None
    if resolved_mode == "service":
        db_for_service = SessionLocal()

    try:
        for scenario_name, profile_types in DEFAULT_SCENARIOS:
            scenarios.append(
                run_single_scenario(
                    config,
                    scenario_name=scenario_name,
                    profile_types=profile_types,
                    db=db_for_service,
                    resolved_mode=resolved_mode,
                )
            )
    finally:
        if db_for_service is not None:
            db_for_service.close()

    full_batch = next(item for item in scenarios if item["name"] == "full_batch")
    summary = {
        "scenario_count": len(scenarios),
        "full_batch_elapsed_ms": full_batch["elapsed_ms"],
        "full_batch_elapsed_seconds": full_batch["elapsed_seconds"],
        "sla_seconds": config.sla_seconds,
        "sla_passed": full_batch["sla_passed"] and full_batch.get("error") is None,
        "sla_failures": [
            f"{item['name']}: {item['elapsed_seconds']}s > {config.sla_seconds}s"
            for item in scenarios
            if not item["sla_passed"] and item.get("error") is None
        ],
        "errors": [item for item in scenarios if item.get("error")],
    }

    return {
        "meta": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "mode": resolved_mode,
            "base_url": config.base_url,
            "tenant_id": config.tenant_id,
            "projects": config.projects,
            "sla_seconds": config.sla_seconds,
        },
        "seed": seed_summary,
        "scenarios": scenarios,
        "summary": summary,
        "notes": notes,
    }
