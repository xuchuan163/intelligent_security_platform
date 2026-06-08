"""Train Bayesian L3 CPT from accident cases (Phase 5 L3-C.2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.session import SessionLocal
from app.services.bayesian.dataset import load_l3_training_rows
from app.services.bayesian.gate import check_l3_case_gate
from app.domain.bayesian.cpt import DEFAULT_CPT_LEARNED_PATH
from app.services.bayesian.training import (
    build_training_rows_from_seeds,
    learn_cpt_from_training_rows,
    write_cpt_learned_file,
)
from app.services.cases.seed_cases import seed_accident_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Bayesian L3 CPT from accident-case labels.")
    parser.add_argument("--tenant-id", default="CSCEC")
    parser.add_argument("--output", type=Path, default=DEFAULT_CPT_LEARNED_PATH)
    parser.add_argument("--alpha", type=float, default=1.0, help="Laplace smoothing strength")
    parser.add_argument("--from-seeds", action="store_true", help="Use in-repo seed cases instead of DB")
    parser.add_argument("--skip-gate", action="store_true", help="Skip active-case count gate check")
    parser.add_argument("--json", action="store_true", help="Print trained metadata as JSON")
    args = parser.parse_args()

    if args.from_seeds:
        training_rows = build_training_rows_from_seeds()
        case_count = len(training_rows)
    else:
        db = SessionLocal()
        try:
            if not args.skip_gate:
                gate = check_l3_case_gate(db, tenant_id=args.tenant_id)
                if not gate["passed"]:
                    print(f"[FAIL] {gate['message']} (cases={gate['case_count']})", file=sys.stderr)
                    return 1
            seed_accident_cases(db)
            training_rows = load_l3_training_rows(db, tenant_id=args.tenant_id)
            case_count = len(training_rows)
        finally:
            db.close()

    payload = learn_cpt_from_training_rows(training_rows, alpha=args.alpha)
    payload["tenant_id"] = args.tenant_id
    payload["case_count"] = case_count
    output = write_cpt_learned_file(payload, args.output)

    if args.json:
        summary = {key: value for key, value in payload.items() if key != "nodes"}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(
            f"[OK] trained {case_count} cases -> {output} "
            f"(version={payload['model_version']}, alpha={args.alpha})"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
