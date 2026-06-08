"""CSV import for accident case library (Phase 4-B.2)."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.database.models import AccidentCaseLibrary
from app.services.cases.milvus_reingest import trigger_accident_case_milvus_reingest

REQUIRED_COLUMNS: tuple[str, ...] = (
    "accident_case_id",
    "tenant_id",
    "accident_type",
    "severity",
)

OPTIONAL_COLUMNS: tuple[str, ...] = (
    "project_type",
    "operation_scene",
    "direct_cause",
    "indirect_cause",
    "involved_subjects",
    "warning_indicators",
    "rectification_measures",
    "tags",
)

ALLOWED_PROJECT_TYPES: frozenset[str] = frozenset(
    {"housing", "municipal", "infrastructure", "mep"}
)

CSV_COLUMNS: tuple[str, ...] = REQUIRED_COLUMNS + OPTIONAL_COLUMNS


class ImportCaseError(ValueError):
    """Raised when a CSV row fails validation."""


@dataclass(frozen=True)
class ImportCaseResult:
    created: int
    updated: int
    skipped: int
    total_rows: int
    milvus_reingest: dict | None = None


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_json_field(raw: str | None, field_name: str, row_number: int) -> Any:
    text = _strip(raw)
    if text is None:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ImportCaseError(
            f"row {row_number}: invalid JSON in {field_name}: {exc.msg}"
        ) from exc


def _parse_tags(raw: str | None) -> list[str] | None:
    text = _strip(raw)
    if text is None:
        return None
    if text.startswith("["):
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError("tags JSON must be a list")
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [part.strip() for part in text.split("|") if part.strip()]


def _validate_row(row: dict[str, str | None], row_number: int) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for column in REQUIRED_COLUMNS:
        value = _strip(row.get(column))
        if not value:
            raise ImportCaseError(f"row {row_number}: missing required field {column}")
        payload[column] = value

    project_type = _strip(row.get("project_type"))
    if project_type is not None and project_type not in ALLOWED_PROJECT_TYPES:
        raise ImportCaseError(
            f"row {row_number}: invalid project_type {project_type!r}, "
            f"expected one of {sorted(ALLOWED_PROJECT_TYPES)}"
        )
    if project_type is not None:
        payload["project_type"] = project_type

    for column in (
        "operation_scene",
        "direct_cause",
        "indirect_cause",
        "rectification_measures",
    ):
        value = _strip(row.get(column))
        if value is not None:
            payload[column] = value

    involved_subjects = _parse_json_field(
        row.get("involved_subjects"), "involved_subjects", row_number
    )
    if involved_subjects is not None:
        payload["involved_subjects"] = involved_subjects

    warning_indicators = _parse_json_field(
        row.get("warning_indicators"), "warning_indicators", row_number
    )
    if warning_indicators is not None:
        payload["warning_indicators"] = warning_indicators

    try:
        tags = _parse_tags(row.get("tags"))
    except (json.JSONDecodeError, ValueError) as exc:
        raise ImportCaseError(f"row {row_number}: invalid tags: {exc}") from exc
    if tags is not None:
        payload["tags"] = tags

    return payload


def _read_csv_rows(path: Path) -> list[dict[str, str | None]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ImportCaseError("CSV header row is missing")
        missing = [column for column in REQUIRED_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ImportCaseError(f"CSV missing required columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def import_accident_cases_from_csv(
    db: Session,
    csv_path: Path,
    *,
    dry_run: bool = False,
    reingest_milvus: bool = False,
) -> ImportCaseResult:
    rows = _read_csv_rows(csv_path)
    created = 0
    updated = 0
    touched_case_ids: list[str] = []
    tenant_ids: set[str] = set()

    for index, row in enumerate(rows, start=2):
        if not any(_strip(value) for value in row.values()):
            continue
        payload = _validate_row(row, index)
        existing = (
            db.query(AccidentCaseLibrary)
            .filter(AccidentCaseLibrary.accident_case_id == payload["accident_case_id"])
            .first()
        )
        if existing is None:
            record = AccidentCaseLibrary(
                accident_case_id=payload["accident_case_id"],
                tenant_id=payload["tenant_id"],
            )
            db.add(record)
            created += 1
        else:
            record = existing
            updated += 1

        for field, value in payload.items():
            setattr(record, field, value)
        record.status = "active"
        record.embedding_version = None
        touched_case_ids.append(payload["accident_case_id"])
        tenant_ids.add(payload["tenant_id"])

    milvus_reingest = None
    if dry_run:
        db.rollback()
    else:
        db.commit()
        if reingest_milvus and tenant_ids:
            tenant_id = next(iter(sorted(tenant_ids)))
            if len(tenant_ids) > 1:
                raise ImportCaseError(
                    "reingest_milvus requires a single tenant_id per import batch; "
                    f"got {sorted(tenant_ids)}"
                )
            milvus_reingest = trigger_accident_case_milvus_reingest(
                db,
                tenant_id=tenant_id,
                accident_case_ids=touched_case_ids,
            )

    return ImportCaseResult(
        created=created,
        updated=updated,
        skipped=0,
        total_rows=len(rows),
        milvus_reingest=milvus_reingest,
    )
