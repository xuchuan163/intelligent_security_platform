"""Run Bayesian L3 calibration backtest and emit report (Phase 5 L3-C.5)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.bayesian.calibration import run_l3_calibration
from app.services.bayesian.training import build_training_rows_from_seeds, write_cpt_learned_file

DEFAULT_REPORT_MD = REPO_ROOT / "docs" / "algo" / "bayesian_l3_backtest.md"
DEFAULT_MIN_HIT_RATE = 0.55


def _to_markdown(report: dict) -> str:
    lines = [
        "# Bayesian L3 Calibration Backtest",
        "",
        f"- Generated at: `{report['meta']['generated_at']}`",
        f"- Source: `{report['meta']['source']}`",
        f"- Train cases: **{report['summary']['train_cases']}**",
        f"- Holdout cases: **{report['summary']['holdout_cases']}**",
        f"- Factor hit rate: **{report['summary']['factor_hit_rate']:.2%}**",
        f"- Outcome Brier score: **{report['summary']['outcome_brier_score']:.4f}** (lower is better)",
        f"- Threshold: factor_hit_rate ≥ {report['summary']['min_factor_hit_rate']:.2%}",
        f"- Result: **{'PASS' if report['summary']['passed'] else 'FAIL'}**",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Bayesian L3 holdout calibration.")
    parser.add_argument("--holdout-ratio", type=float, default=0.2)
    parser.add_argument("--alpha", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-hit-rate", type=float, default=DEFAULT_MIN_HIT_RATE)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_REPORT_MD)
    parser.add_argument("--json-out", type=Path, help="Optional JSON report path")
    parser.add_argument("--write-cpt", type=Path, help="Optional path to write trained CPT JSON")
    args = parser.parse_args()

    training_rows = build_training_rows_from_seeds()
    calibration = run_l3_calibration(
        training_rows,
        holdout_ratio=args.holdout_ratio,
        alpha=args.alpha,
        seed=args.seed,
        min_factor_hit_rate=args.min_hit_rate,
    )

    if args.write_cpt:
        write_cpt_learned_file(calibration["cpt_payload"], args.write_cpt)

    report = {
        "meta": {
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "source": "seed_cases",
            "holdout_ratio": args.holdout_ratio,
            "alpha": args.alpha,
            "seed": args.seed,
        },
        "summary": {
            "train_cases": calibration["train_cases"],
            "holdout_cases": calibration["holdout_cases"],
            "factor_hit_rate": calibration["factor_hit_rate"],
            "outcome_brier_score": calibration["outcome_brier_score"],
            "min_factor_hit_rate": calibration["min_factor_hit_rate"],
            "passed": calibration["passed"],
        },
    }

    markdown = _to_markdown(report)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.write_text(markdown, encoding="utf-8")

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if calibration["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
