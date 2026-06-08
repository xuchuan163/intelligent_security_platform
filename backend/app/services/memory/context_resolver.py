from __future__ import annotations

import re
from typing import Any

ENTITY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("project_id", r"\bP\d{3}\b"),
    ("hazard_id", r"\bH\d{3}\b"),
    ("work_order_id", r"\bWO[-A-Z0-9]+\b"),
    ("rule_id", r"\bSR-(?:PROJ|WORKER|SUB)-\d{3}\b"),
    ("metric_code", r"\bM-[A-Z0-9_-]+\b"),
    ("worker_id", r"\bW\d{3}\b"),
    ("subcontractor_id", r"\bSC\d{3}\b"),
)


def merge_session_context(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for key, value in incoming.items():
        if value is not None:
            merged[key] = value
    return merged


def extract_explicit_entities(text: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for field, pattern in ENTITY_PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match is not None:
            found[field] = match.group(0).upper() if field == "work_order_id" else match.group(0)
    return found


def resolve_follow_up_context(
    memory: dict[str, Any],
    *,
    follow_up_message: str | None = None,
) -> dict[str, Any]:
    resolved = dict(memory.get("context") or {})
    if follow_up_message:
        resolved.update(extract_explicit_entities(follow_up_message))
    return resolved
