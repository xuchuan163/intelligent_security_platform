import json
from pathlib import Path
from typing import Any

from app.core.security import MockUser
from app.services.nl2sql.generator import MockCandidateSqlProvider, generate_candidate_sql

VALID_GENERATION_STATUSES = {"audit_passed", "audit_rejected", "clarification_required"}


def load_benchmark_cases(path: str | Path) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    return [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)


def _contains_all(haystack: str | None, fragments: list[str]) -> list[str]:
    text = haystack or ""
    return [fragment for fragment in fragments if fragment not in text]


def _contains_forbidden(haystack: str | None, fragments: list[str]) -> list[str]:
    text = haystack or ""
    return [fragment for fragment in fragments if fragment and fragment in text]


def _evaluate_case(case: dict[str, Any], current_user: MockUser) -> dict[str, Any]:
    result = generate_candidate_sql(
        question=case["question"],
        current_user=current_user,
        provider=MockCandidateSqlProvider(case.get("mock_llm_output", "")),
    )
    errors: list[str] = []

    if result.status != case["expected_status"]:
        errors.append(f"status expected {case['expected_status']} got {result.status}")

    expected_tables = set(case.get("expected_tables", []))
    if expected_tables and set(result.tables_used) != expected_tables:
        errors.append(f"tables expected {sorted(expected_tables)} got {result.tables_used}")

    expected_fields = set(case.get("expected_fields", []))
    if expected_fields and set(result.fields_used) != expected_fields:
        errors.append(f"fields expected {sorted(expected_fields)} got {result.fields_used}")

    checked_sql = result.sanitized_sql or result.candidate_sql or ""
    missing_fragments = _contains_all(checked_sql, case.get("expected_contains", []))
    if missing_fragments:
        errors.append(f"missing SQL fragments: {missing_fragments}")

    forbidden_fragments = _contains_forbidden(result.sanitized_sql, case.get("forbidden_contains", []))
    if forbidden_fragments:
        errors.append(f"forbidden SQL fragments present: {forbidden_fragments}")

    return {
        "case": case,
        "result": result,
        "passed": not errors,
        "errors": errors,
    }


def _new_category_summary() -> dict[str, int]:
    return {"total": 0, "passed": 0, "failed": 0}


def run_nl2sql_benchmark(cases: list[dict[str, Any]], current_user: MockUser) -> dict[str, Any]:
    evaluations = [_evaluate_case(case, current_user) for case in cases]
    total_cases = len(evaluations)
    passed_cases = sum(1 for item in evaluations if item["passed"])
    failures = [
        {
            "case_id": item["case"]["case_id"],
            "category": item["case"]["category"],
            "errors": item["errors"],
            "actual_status": item["result"].status,
        }
        for item in evaluations
        if not item["passed"]
    ]

    generation_valid = sum(1 for item in evaluations if item["result"].status in VALID_GENERATION_STATUSES)
    legal_expected = [item for item in evaluations if item["case"]["expected_status"] == "audit_passed"]
    legal_passed = sum(1 for item in legal_expected if item["result"].status == "audit_passed")
    unsafe_expected = [
        item
        for item in evaluations
        if item["case"]["category"].startswith("unsafe_")
    ]
    unsafe_blocked = sum(
        1
        for item in unsafe_expected
        if item["result"].status in {"audit_rejected", "invalid_output", "generation_failed"}
    )
    clarification_expected = [item for item in evaluations if item["case"].get("requires_clarification")]
    clarification_returned = sum(
        1 for item in clarification_expected if item["result"].status == "clarification_required"
    )
    invalid_expected = [
        item
        for item in evaluations
        if item["case"]["expected_status"] in {"invalid_output", "generation_failed"}
    ]
    invalid_blocked = sum(
        1 for item in invalid_expected if item["result"].status in {"invalid_output", "generation_failed"}
    )

    category_summary: dict[str, dict[str, int]] = {}
    for item in evaluations:
        category = item["case"]["category"]
        summary = category_summary.setdefault(category, _new_category_summary())
        summary["total"] += 1
        if item["passed"]:
            summary["passed"] += 1
        else:
            summary["failed"] += 1

    return {
        "total_cases": total_cases,
        "passed_cases": passed_cases,
        "failed_cases": total_cases - passed_cases,
        "generation_valid_rate": _rate(generation_valid, total_cases),
        "audit_pass_rate": _rate(legal_passed, len(legal_expected)),
        "unsafe_block_rate": _rate(unsafe_blocked, len(unsafe_expected)),
        "clarification_rate": _rate(clarification_returned, len(clarification_expected)),
        "invalid_output_block_rate": _rate(invalid_blocked, len(invalid_expected)),
        "category_summary": category_summary,
        "failures": failures,
    }
