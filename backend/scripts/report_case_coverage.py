"""Report accident-case coverage for Bayesian L3 (Phase 5 L3-0.2)."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import SessionLocal


def _non_empty_rate(rows: list[AccidentCaseLibrary], field: str) -> float:
    if not rows:
        return 0.0
    filled = 0
    for row in rows:
        value = getattr(row, field, None)
        if isinstance(value, str) and value.strip():
            filled += 1
        elif isinstance(value, list) and value:
            filled += 1
        elif isinstance(value, dict) and value:
            filled += 1
    return round(filled / len(rows), 4)


def build_coverage_report(*, tenant_id: str | None = None) -> dict[str, Any]:
    db = SessionLocal()
    try:
        query = db.query(AccidentCaseLibrary).filter(AccidentCaseLibrary.status == "active")
        if tenant_id:
            query = query.filter(AccidentCaseLibrary.tenant_id == tenant_id)
        rows = query.order_by(AccidentCaseLibrary.accident_case_id.asc()).all()
    finally:
        db.close()

    accident_types = Counter(row.accident_type for row in rows)
    project_types = Counter(row.project_type for row in rows)
    severities = Counter(row.severity for row in rows)

    return {
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "tenant_id": tenant_id,
        "total_active_cases": len(rows),
        "accident_type_counts": dict(sorted(accident_types.items())),
        "project_type_counts": dict(sorted(project_types.items())),
        "severity_counts": dict(sorted(severities.items())),
        "field_fill_rates": {
            "direct_cause": _non_empty_rate(rows, "direct_cause"),
            "indirect_cause": _non_empty_rate(rows, "indirect_cause"),
            "tags": _non_empty_rate(rows, "tags"),
            "warning_indicators": _non_empty_rate(rows, "warning_indicators"),
        },
    }


def _to_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Accident Case Coverage Report",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Tenant: `{report.get('tenant_id') or 'ALL'}`",
        f"- Active cases: **{report['total_active_cases']}**",
        "",
        "## Accident types",
        "",
    ]
    for key, value in report["accident_type_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Project types", ""])
    for key, value in report["project_type_counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Field fill rates", ""])
    for key, value in report["field_fill_rates"].items():
        lines.append(f"- {key}: {value:.1%}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit accident-case coverage for L3 readiness.")
    parser.add_argument("--tenant-id", default="CSCEC")
    parser.add_argument("--json-out", type=Path, help="Write JSON report to path")
    parser.add_argument("--md-out", type=Path, help="Write markdown report to path")
    args = parser.parse_args()

    report = build_coverage_report(tenant_id=args.tenant_id)
    markdown = _to_markdown(report)

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(markdown, encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
