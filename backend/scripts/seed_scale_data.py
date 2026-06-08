"""Seed synthetic scale data for performance tests (Phase 4-C.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.session import SessionLocal
from app.services.scale.seed_scale_data import ScaleSeedConfig, seed_scale_data


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed synthetic projects/workers/subcontractors.")
    parser.add_argument("--projects", type=int, default=100, help="Number of projects to seed.")
    parser.add_argument(
        "--tenant-id",
        default="CSCEC-SCALE",
        help="Isolated tenant id for scale data (default: CSCEC-SCALE).",
    )
    parser.add_argument(
        "--subcontractors-per-project",
        type=int,
        default=2,
        help="Subcontractors created per project.",
    )
    parser.add_argument(
        "--workers-per-project",
        type=int,
        default=8,
        help="Workers created per project.",
    )
    parser.add_argument(
        "--no-profiles",
        action="store_true",
        help="Skip risk profile upserts for faster seeding.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=20260603,
        help="Deterministic random seed.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=200,
        help="Commit every N projects.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write JSON summary.",
    )
    args = parser.parse_args()

    config = ScaleSeedConfig(
        tenant_id=args.tenant_id,
        project_count=args.projects,
        subcontractors_per_project=args.subcontractors_per_project,
        workers_per_project=args.workers_per_project,
        with_profiles=not args.no_profiles,
        random_seed=args.random_seed,
        batch_size=args.batch_size,
    )

    db = SessionLocal()
    try:
        result = seed_scale_data(db, config)
    except ValueError as exc:
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()

    payload = result.as_dict()
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
