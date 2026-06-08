"""Run profile recalculate batch benchmark and write perf reports (Phase 4-C.6)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.scale.pool_tuning import (
    build_pool_tuning_recommendations,
    render_pool_tuning_markdown,
    render_recalculate_benchmark_markdown,
)
from app.services.scale.profile_recalculate_benchmark import (
    RecalculateBenchmarkConfig,
    run_profile_recalculate_benchmark,
)

DEFAULT_JSON = REPO_ROOT / "docs" / "perf" / "profile_recalculate_benchmark.json"
DEFAULT_MD = REPO_ROOT / "docs" / "perf" / "profile_recalculate_benchmark.md"
DEFAULT_POOL_MD = REPO_ROOT / "docs" / "perf" / "DB_POOL_TUNING.md"


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark POST /profile/recalculate batch timing.")
    parser.add_argument("--projects", type=int, default=500)
    parser.add_argument("--tenant-id", default="CSCEC-SCALE")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--sla-seconds", type=float, default=30.0)
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--skip-seed", action="store_true")
    parser.add_argument("--id-prefix", default="SCALE")
    parser.add_argument("--enforce-sla", action="store_true")
    parser.add_argument("--json-output", default=str(DEFAULT_JSON))
    parser.add_argument("--md-output", default=str(DEFAULT_MD))
    parser.add_argument("--pool-md-output", default=str(DEFAULT_POOL_MD))
    args = parser.parse_args()

    benchmark = run_profile_recalculate_benchmark(
        RecalculateBenchmarkConfig(
            tenant_id=args.tenant_id,
            projects=args.projects,
            skip_seed=args.skip_seed,
            sla_seconds=args.sla_seconds,
            base_url=args.base_url,
            timeout_seconds=args.timeout,
            seed_batch_size=50 if args.projects >= 1000 else 200,
            id_prefix=args.id_prefix,
        )
    )
    pool_tuning = build_pool_tuning_recommendations(benchmark)

    payload = {
        "title": f"Phase 4-C.6 profile/recalculate 批量耗时 — {args.projects} 项目",
        "benchmark": benchmark,
        "pool_tuning": pool_tuning,
    }

    json_output = Path(args.json_output)
    md_output = Path(args.md_output)
    pool_md_output = Path(args.pool_md_output)
    for path in (json_output, md_output, pool_md_output):
        path.parent.mkdir(parents=True, exist_ok=True)

    json_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_output.write_text(
        render_recalculate_benchmark_markdown(
            title=f"Phase 4 画像重算基线 — {args.projects} 项目",
            benchmark=benchmark,
            pool_tuning=pool_tuning,
        ),
        encoding="utf-8",
    )
    pool_md_output.write_text(render_pool_tuning_markdown(pool_tuning), encoding="utf-8")

    print(json.dumps(benchmark["summary"], ensure_ascii=False, indent=2))
    print(f"json={json_output}")
    print(f"markdown={md_output}")
    print(f"pool_tuning={pool_md_output}")

    exit_code = 0
    if benchmark["summary"].get("errors"):
        exit_code = 1
    if args.enforce_sla and not benchmark["summary"].get("sla_passed"):
        exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
