"""Import accident cases from CSV (Phase 4-B.2)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.session import SessionLocal
from app.services.cases.import_cases import ImportCaseError, import_accident_cases_from_csv

DEFAULT_TEMPLATE = BACKEND_ROOT.parent / "config" / "cases" / "accident_cases_template.csv"


def main() -> int:
    parser = argparse.ArgumentParser(description="Import accident cases from CSV.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default=str(DEFAULT_TEMPLATE),
        help="Path to CSV file (default: config/cases/accident_cases_template.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and simulate import without committing.",
    )
    parser.add_argument(
        "--reingest-milvus",
        action="store_true",
        help="After successful import, trigger Milvus accident-case re-ingest.",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        result = import_accident_cases_from_csv(
            db,
            csv_path,
            dry_run=args.dry_run,
            reingest_milvus=args.reingest_milvus,
        )
    except ImportCaseError as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    mode = "dry-run" if args.dry_run else "committed"
    print(
        f"[{mode}] rows={result.total_rows} created={result.created} "
        f"updated={result.updated} file={csv_path}"
    )
    if result.milvus_reingest is not None:
        print(f"milvus_reingest={result.milvus_reingest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
