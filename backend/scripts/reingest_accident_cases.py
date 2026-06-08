"""Re-ingest accident cases into Milvus (Phase 4-B.6)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.session import SessionLocal
from app.services.cases.milvus_reingest import trigger_accident_case_milvus_reingest
from app.services.cases.seed_cases import seed_accident_cases


def main() -> int:
    parser = argparse.ArgumentParser(description="Re-ingest accident cases into Milvus.")
    parser.add_argument(
        "--tenant-id",
        default="CSCEC",
        help="Tenant scope for re-ingest (default: CSCEC).",
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Seed demo accident cases before re-ingest.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write JSON result.",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.seed:
            seed_accident_cases(db)
        result = trigger_accident_case_milvus_reingest(db, tenant_id=args.tenant_id)
    finally:
        db.close()

    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)

    if result["status"] == "skipped" and result["reason"] == "milvus_disabled":
        return 2
    if result["status"] == "skipped":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
