"""Run accident-case backtest and emit JSON report (Phase 4-B.5)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.session import SessionLocal
from app.services.cases.backtest import (
    DEFAULT_DATASET_PATH,
    load_case_backtest_cases,
    run_case_backtest,
    run_case_backtest_from_db,
)
from app.services.cases.seed_cases import seed_accident_cases

DEFAULT_MIN_HIT_RATE = 0.6


def _build_report_payload(
    report: dict[str, Any],
    *,
    source: str,
    dataset_path: Path | None,
    tenant_id: str | None,
    min_hit_rate: float,
) -> dict[str, Any]:
    return {
        "meta": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": source,
            "dataset_path": str(dataset_path) if dataset_path else None,
            "tenant_id": tenant_id,
            "min_hit_rate": min_hit_rate,
        },
        "summary": {
            "total_cases": report["total_cases"],
            "passed_cases": report["passed_cases"],
            "failed_cases": report["failed_cases"],
            "hit_rate": report["hit_rate"],
            "rule_hit_rate": report["rule_hit_rate"],
            "risk_level_hit_rate": report["risk_level_hit_rate"],
            "tag_hit_rate": report["tag_hit_rate"],
            "coverage": report["coverage"],
        },
        "evaluations": report["evaluations"],
    }


def run_dataset_backtest(dataset_path: Path) -> dict[str, Any]:
    cases = load_case_backtest_cases(dataset_path)
    if not cases:
        raise ValueError(f"dataset is empty or missing: {dataset_path}")
    return run_case_backtest(cases)


def run_db_backtest(*, tenant_id: str | None, seed: bool) -> dict[str, Any]:
    db = SessionLocal()
    try:
        if seed:
            seed_accident_cases(db)
        return run_case_backtest_from_db(db, tenant_id=tenant_id)
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run case backtest and output JSON report.")
    parser.add_argument(
        "--source",
        choices=("dataset", "db"),
        default="dataset",
        help="Backtest source: fixed dataset (default) or accident_case_library table.",
    )
    parser.add_argument(
        "--dataset",
        default=str(DEFAULT_DATASET_PATH),
        help="Path to case_backtest JSONL when --source=dataset.",
    )
    parser.add_argument(
        "--tenant-id",
        default=None,
        help="Tenant filter when --source=db.",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed demo accident cases before DB backtest.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write JSON report.",
    )
    parser.add_argument(
        "--min-hit-rate",
        type=float,
        default=DEFAULT_MIN_HIT_RATE,
        help=f"Exit code 1 if hit_rate is below this threshold (default: {DEFAULT_MIN_HIT_RATE}).",
    )
    args = parser.parse_args(argv)

    dataset_path = Path(args.dataset) if args.source == "dataset" else None
    try:
        if args.source == "dataset":
            if dataset_path is None or not dataset_path.is_file():
                print(f"Dataset not found: {dataset_path}", file=sys.stderr)
                return 1
            report = run_dataset_backtest(dataset_path)
        else:
            report = run_db_backtest(tenant_id=args.tenant_id, seed=args.seed)
    except ValueError as exc:
        print(f"Backtest failed: {exc}", file=sys.stderr)
        return 1

    payload = _build_report_payload(
        report,
        source=args.source,
        dataset_path=dataset_path,
        tenant_id=args.tenant_id,
        min_hit_rate=args.min_hit_rate,
    )
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")

    print(rendered)
    return 0 if report["hit_rate"] >= args.min_hit_rate else 1


if __name__ == "__main__":
    raise SystemExit(main())
