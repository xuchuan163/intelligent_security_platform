"""Check Bayesian L3 case-count gate (Phase 5 L3-0.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.session import SessionLocal
from app.services.bayesian.gate import L3_MIN_CASES, check_l3_case_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Check active accident-case count for Bayesian L3.")
    parser.add_argument("--tenant-id", default="CSCEC", help="Tenant id to check")
    parser.add_argument("--min-cases", type=int, default=L3_MIN_CASES, help="Minimum active cases")
    parser.add_argument("--json", action="store_true", help="Emit JSON payload to stdout")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = check_l3_case_gate(db, tenant_id=args.tenant_id, min_cases=args.min_cases)
    finally:
        db.close()

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        status = "PASS" if result["passed"] else "FAIL"
        print(
            f"[{status}] tenant={result['tenant_id']} "
            f"cases={result['case_count']}/{result['min_cases']} — {result['message']}"
        )
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
