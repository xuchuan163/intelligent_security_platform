import json
from pathlib import Path

from app.core.security import DataScope, MockUser
from app.services.nl2sql.benchmark import load_benchmark_cases, run_nl2sql_benchmark


DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "nl2sql_100.jsonl"


def _tenant_user() -> MockUser:
    return MockUser(
        user_id="u-nl2sql-bench-001",
        user_name="NL2SQL Benchmark User",
        tenant_id="TENANT-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
    )


def test_nl2sql_100_dataset_has_required_size_schema_and_categories():
    cases = [json.loads(line) for line in DATASET_PATH.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    categories = {case["category"] for case in cases}
    required_keys = {
        "case_id",
        "category",
        "question",
        "mock_llm_output",
        "expected_status",
        "expected_tables",
        "expected_fields",
        "expected_contains",
        "forbidden_contains",
        "requires_clarification",
        "difficulty",
    }

    assert len(cases) >= 100
    assert all(required_keys <= set(case) for case in cases)
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {
        "valid_project",
        "valid_worker",
        "valid_metric",
        "valid_join",
        "clarification_required",
        "unsafe_write",
        "unsafe_sensitive_field",
        "unsafe_internal_table",
        "invalid_output",
    } <= categories
    assert all(
        "tenant_id" not in fragment and "org_path" not in fragment
        for case in cases
        for fragment in case["expected_contains"]
    )


def test_benchmark_runner_reports_rates_and_no_failures_for_static_dataset():
    cases = load_benchmark_cases(DATASET_PATH)

    report = run_nl2sql_benchmark(cases, current_user=_tenant_user())

    assert report["total_cases"] >= 100
    assert report["passed_cases"] == report["total_cases"]
    assert report["failed_cases"] == 0
    assert report["unsafe_block_rate"] == 1.0
    assert report["invalid_output_block_rate"] == 1.0
    assert report["clarification_rate"] == 1.0
    assert report["generation_valid_rate"] >= 0.8
    assert report["audit_pass_rate"] >= 0.95
    assert report["failures"] == []
    assert report["category_summary"]["valid_project"]["total"] >= 1
    assert report["category_summary"]["unsafe_write"]["total"] >= 1


def test_benchmark_runner_detects_status_and_sql_fragment_failures():
    broken_case = {
        "case_id": "BROKEN-001",
        "category": "valid_project",
        "question": "List active projects",
        "mock_llm_output": "select project_id from project where status = 'active'",
        "expected_status": "audit_rejected",
        "expected_tables": [],
        "expected_fields": [],
        "expected_contains": ["not-present-fragment"],
        "forbidden_contains": ["tenant_id"],
        "requires_clarification": False,
        "difficulty": "easy",
    }

    report = run_nl2sql_benchmark([broken_case], current_user=_tenant_user())

    assert report["total_cases"] == 1
    assert report["passed_cases"] == 0
    assert report["failed_cases"] == 1
    assert report["failures"][0]["case_id"] == "BROKEN-001"
    assert "status expected audit_rejected got audit_passed" in report["failures"][0]["errors"]
