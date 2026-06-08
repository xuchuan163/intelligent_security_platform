"""Run API load test and emit JSON latency report (Phase 4-C.2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.scale.load_test_api import (
    LoadTestConfig,
    build_httpx_request_fn,
    build_load_test_headers,
    run_api_load_test,
)

DEFAULT_MAX_ERROR_RATE = 0.001


def main() -> int:
    parser = argparse.ArgumentParser(description="Load test key dashboard/list APIs.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="API base URL.")
    parser.add_argument("--tenant-id", default="CSCEC-SCALE", help="Tenant header value.")
    parser.add_argument("--iterations", type=int, default=30, help="Requests per endpoint.")
    parser.add_argument("--concurrency", type=int, default=4, help="Parallel workers per endpoint.")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP timeout seconds.")
    parser.add_argument(
        "--max-error-rate",
        type=float,
        default=DEFAULT_MAX_ERROR_RATE,
        help="Exit 1 if overall error_rate exceeds this value.",
    )
    parser.add_argument("--output", default=None, help="Optional JSON report path.")
    args = parser.parse_args()

    config = LoadTestConfig(
        base_url=args.base_url.rstrip("/"),
        tenant_id=args.tenant_id,
        iterations=args.iterations,
        concurrency=args.concurrency,
        timeout_seconds=args.timeout,
    )
    headers = build_load_test_headers(tenant_id=config.tenant_id)
    request_fn = build_httpx_request_fn(
        base_url=config.base_url,
        headers=headers,
        timeout_seconds=config.timeout_seconds,
    )

    try:
        report = run_api_load_test(request_fn, config=config)
    except ValueError as exc:
        print(f"Load test failed: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if report["summary"]["error_rate"] > args.max_error_rate:
        return 1
    if not report["summary"]["sla_passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
