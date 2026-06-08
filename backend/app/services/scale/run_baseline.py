"""Shared orchestration for scale performance baselines (Phase 4-C.3+)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.infrastructure.database.session import SessionLocal
from app.main import app
from app.services.scale.baseline_report import render_baseline_markdown
from app.services.scale.load_test_api import (
    LoadTestConfig,
    build_httpx_request_fn,
    build_load_test_headers,
    build_test_client_request_fn,
    run_api_load_test,
)
from app.services.scale.seed_scale_data import ScaleSeedConfig, seed_scale_data


@dataclass(frozen=True)
class BaselineRunConfig:
    projects: int
    tenant_id: str
    markdown_title: str
    payload_title: str
    json_output: Path
    md_output: Path
    base_url: str = "http://127.0.0.1:8000"
    iterations: int = 30
    concurrency: int = 4
    timeout_seconds: float = 30.0
    skip_seed: bool = False
    subcontractors_per_project: int = 2
    workers_per_project: int = 8
    seed_batch_size: int = 200
    id_prefix: str = "SCALE"
    max_error_rate: float = 0.001
    enforce_sla: bool = True


def probe_http(base_url: str, tenant_id: str, timeout: float) -> bool:
    import httpx

    headers = build_load_test_headers(tenant_id=tenant_id)
    try:
        with httpx.Client(base_url=base_url, headers=headers, timeout=timeout) as client:
            response = client.get("/api/v1/dashboard/overview")
            return response.status_code == 200
    except httpx.HTTPError:
        return False


def run_performance_baseline(config: BaselineRunConfig) -> tuple[int, dict[str, Any]]:
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

    load_config = LoadTestConfig(
        base_url=config.base_url.rstrip("/"),
        tenant_id=config.tenant_id,
        iterations=config.iterations,
        concurrency=config.concurrency,
        timeout_seconds=config.timeout_seconds,
    )
    notes: list[str] = []
    if probe_http(load_config.base_url, load_config.tenant_id, load_config.timeout_seconds):
        request_fn = build_httpx_request_fn(
            base_url=load_config.base_url,
            headers=build_load_test_headers(tenant_id=load_config.tenant_id),
            timeout_seconds=load_config.timeout_seconds,
        )
        mode = "http"
        notes.append("压测通过 HTTP 访问运行中的 API 服务。")
    else:
        client = TestClient(app)
        for header, value in build_load_test_headers(tenant_id=load_config.tenant_id).items():
            client.headers[header] = value
        request_fn = build_test_client_request_fn(client)
        mode = "in_process_testclient"
        notes.append(
            f"未检测到可访问的 API（{load_config.base_url}），回退为 TestClient 进程内压测；"
            "P95 仅供参考，生产级基线请在独立压测环境对 HTTP 服务复测。"
        )
    if config.projects >= 2000:
        notes.append(
            "2000 项目为目标规模压测（4-C.5），SLA 参照 500 项目门禁，"
            "结果用于容量规划而非发布阻断。"
        )

    load_report = run_api_load_test(request_fn, config=load_config)
    load_report["meta"]["mode"] = mode
    load_report["seed"] = seed_summary

    payload = {
        "title": config.payload_title,
        "seed": seed_summary,
        "load_test": load_report,
    }

    config.json_output.parent.mkdir(parents=True, exist_ok=True)
    config.md_output.parent.mkdir(parents=True, exist_ok=True)
    config.json_output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config.md_output.write_text(
        render_baseline_markdown(
            title=config.markdown_title,
            seed_summary=seed_summary,
            load_report=load_report,
            notes=notes,
        ),
        encoding="utf-8",
    )

    exit_code = 0
    if load_report["summary"]["error_rate"] > config.max_error_rate:
        exit_code = 1
    if config.enforce_sla and not load_report["summary"]["sla_passed"]:
        exit_code = 1
    return exit_code, payload
