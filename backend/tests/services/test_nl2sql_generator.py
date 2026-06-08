import json
from pathlib import Path

from app.core.security import DataScope, MockUser, ScopeType
from app.services.nl2sql.generator import MockCandidateSqlProvider, generate_candidate_sql


DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "nl2sql_generation_cases.jsonl"


def _tenant_user() -> MockUser:
    return MockUser(
        user_id="u-nl2sql-gen-001",
        user_name="NL2SQL Generator User",
        tenant_id="TENANT-A",
        company_id="COMPANY-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def _cases() -> list[dict]:
    return [json.loads(line) for line in DATASET_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_nl2sql_generation_dataset_covers_generation_and_audit_edges():
    cases = _cases()
    categories = {case["category"] for case in cases}

    assert len(cases) >= 12
    assert {
        "valid_project",
        "valid_worker",
        "valid_hazard",
        "valid_metric_alias",
        "ambiguous_time",
        "invalid_markdown",
        "invalid_explanation",
        "audit_reject_tenant",
        "audit_reject_table",
        "audit_reject_field",
        "invalid_multi_statement",
        "empty_output",
    } <= categories


def test_generator_returns_audit_passed_for_valid_mock_sql():
    provider = MockCandidateSqlProvider("select project_id, project_name from project where status = 'active'")

    result = generate_candidate_sql(
        question="List active projects",
        current_user=_tenant_user(),
        provider=provider,
    )

    assert result.status == "audit_passed"
    assert result.candidate_sql == "select project_id, project_name from project where status = 'active'"
    assert result.sanitized_sql is not None
    assert "project.company_id = 'COMPANY-A'" in result.sanitized_sql
    assert "tenant_id" not in result.sanitized_sql
    assert "LIMIT 100" in result.sanitized_sql
    assert result.tables_used == ["project"]
    assert result.fields_used == ["project_id", "project_name", "status"]
    assert result.rejection_reason is None


def test_generator_rejects_markdown_or_explained_outputs_before_audit():
    markdown_result = generate_candidate_sql(
        question="List projects",
        current_user=_tenant_user(),
        provider=MockCandidateSqlProvider("```sql\nselect project_id from project\n```"),
    )
    explained_result = generate_candidate_sql(
        question="List projects",
        current_user=_tenant_user(),
        provider=MockCandidateSqlProvider("Here is the SQL: select project_id from project"),
    )

    assert markdown_result.status == "invalid_output"
    assert markdown_result.candidate_sql is None
    assert "plain SQL" in markdown_result.rejection_reason
    assert explained_result.status == "invalid_output"
    assert explained_result.candidate_sql is None


def test_generator_maps_refusal_token_to_clarification_required():
    result = generate_candidate_sql(
        question="Show recent severe projects",
        current_user=_tenant_user(),
        provider=MockCandidateSqlProvider("CLARIFICATION_REQUIRED: please provide a time range"),
    )

    assert result.status == "clarification_required"
    assert result.candidate_sql is None
    assert "time range" in result.rejection_reason


def test_generator_returns_audit_rejected_for_unsafe_sql():
    result = generate_candidate_sql(
        question="Read worker identity cards",
        current_user=_tenant_user(),
        provider=MockCandidateSqlProvider("select identity_card from worker"),
    )

    assert result.status == "audit_rejected"
    assert result.candidate_sql == "select identity_card from worker"
    assert result.sanitized_sql is None
    assert result.rejection_reason == "field not allowed: worker.identity_card"


def test_generator_returns_generation_failed_for_empty_output_or_provider_error():
    empty_result = generate_candidate_sql(
        question="List projects",
        current_user=_tenant_user(),
        provider=MockCandidateSqlProvider(""),
    )
    error_result = generate_candidate_sql(
        question="List projects",
        current_user=_tenant_user(),
        provider=MockCandidateSqlProvider(error=RuntimeError("timeout")),
    )

    assert empty_result.status == "generation_failed"
    assert empty_result.candidate_sql is None
    assert "empty" in empty_result.rejection_reason
    assert error_result.status == "generation_failed"
    assert error_result.candidate_sql is None
    assert "timeout" in error_result.rejection_reason


def test_generation_cases_match_expected_statuses():
    for case in _cases():
        result = generate_candidate_sql(
            question=case["question"],
            current_user=_tenant_user(),
            provider=MockCandidateSqlProvider(case["mock_llm_output"]),
        )

        assert result.status == case["expected_status"], case["case_id"]
        if result.status == "audit_passed":
            assert result.tables_used == case["expected_tables"]
            assert result.fields_used == case["expected_fields"]
            for fragment in case["expected_contains"]:
                assert fragment in result.sanitized_sql
