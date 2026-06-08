"""Run 500-project gate load baseline and write perf report (Phase 4-C.4)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.scale.run_baseline import BaselineRunConfig, run_performance_baseline

DEFAULT_JSON = REPO_ROOT / "docs" / "perf" / "baseline_500.json"
DEFAULT_MD = REPO_ROOT / "docs" / "perf" / "baseline_500.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed 500 projects and run gate load baseline.")
    parser.add_argument("--projects", type=int, default=500)
    parser.add_argument("--tenant-id", default="CSCEC-SCALE")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--iterations", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--id-prefix", default="SCALE")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON))
    parser.add_argument("--md-output", default=str(DEFAULT_MD))
    args = parser.parse_args()

    exit_code, payload = run_performance_baseline(
        BaselineRunConfig(
            projects=args.projects,
            tenant_id=args.tenant_id,
            markdown_title="Phase 4 性能基线 — 500 项目门禁压测",
            payload_title="Phase 4-C.4 500 项目门禁压测基线",
            json_output=Path(args.json_output),
            md_output=Path(args.md_output),
            base_url=args.base_url,
            iterations=args.iterations,
            concurrency=args.concurrency,
            timeout_seconds=args.timeout,
            skip_seed=args.skip_seed,
            seed_batch_size=100,
            id_prefix=args.id_prefix,
        )
    )
    print(json.dumps(payload["load_test"]["summary"], ensure_ascii=False, indent=2))
    print(f"json={args.json_output}")
    print(f"markdown={args.md_output}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
