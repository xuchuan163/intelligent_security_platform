from app.core.security import DataScope, MockUser
from app.services.nl2sql.generator import generate_candidate_sql
from app.services.nl2sql.providers import (
    DisabledCandidateSqlProvider,
    QwenCandidateSqlProvider,
    build_candidate_sql_provider,
)


class FakeQwenClient:
    def __init__(self, content: str | None = None, available: bool = True, error: Exception | None = None) -> None:
        self.content = content
        self.available = available
        self.error = error
        self.calls: list[dict] = []

    def chat(self, messages: list[dict], temperature: float = 0.0, timeout_seconds: int | None = None) -> dict:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error is not None:
            raise self.error
        return {
            "available": self.available,
            "message": "ok" if self.available else "not configured",
            "content": self.content,
        }


def _tenant_user() -> MockUser:
    return MockUser(
        user_id="u-nl2sql-qwen-001",
        user_name="NL2SQL Qwen User",
        tenant_id="TENANT-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
    )


def test_qwen_provider_missing_api_key_degrades_to_generation_failed():
    provider = QwenCandidateSqlProvider(FakeQwenClient(available=False))

    result = generate_candidate_sql(
        question="List active projects",
        current_user=_tenant_user(),
        provider=provider,
    )

    assert result.status == "generation_failed"
    assert result.candidate_sql is None
    assert "not configured" in result.rejection_reason


def test_qwen_provider_timeout_or_exception_maps_to_generation_failed():
    provider = QwenCandidateSqlProvider(FakeQwenClient(error=TimeoutError("qwen timeout")))

    result = generate_candidate_sql(
        question="List active projects",
        current_user=_tenant_user(),
        provider=provider,
    )

    assert result.status == "generation_failed"
    assert result.candidate_sql is None
    assert "qwen timeout" in result.rejection_reason


def test_qwen_provider_sql_output_still_flows_through_audit_sql():
    fake_client = FakeQwenClient("select project_id, project_name from project where status = 'active'")
    provider = QwenCandidateSqlProvider(fake_client, timeout_seconds=7)

    result = generate_candidate_sql(
        question="List active projects",
        current_user=_tenant_user(),
        provider=provider,
    )

    assert result.status == "audit_passed"
    assert result.candidate_sql == "select project_id, project_name from project where status = 'active'"
    assert "project.company_id = 'TENANT-A'" in result.sanitized_sql
    assert "LIMIT 100" in result.sanitized_sql
    assert fake_client.calls[0]["temperature"] == 0.0
    assert fake_client.calls[0]["timeout_seconds"] == 7


def test_qwen_provider_markdown_or_explanation_output_is_rejected():
    markdown_result = generate_candidate_sql(
        question="List projects",
        current_user=_tenant_user(),
        provider=QwenCandidateSqlProvider(FakeQwenClient("```sql\nselect project_id from project\n```")),
    )
    explanation_result = generate_candidate_sql(
        question="List projects",
        current_user=_tenant_user(),
        provider=QwenCandidateSqlProvider(FakeQwenClient("Here is the SQL: select project_id from project")),
    )

    assert markdown_result.status == "invalid_output"
    assert markdown_result.candidate_sql is None
    assert explanation_result.status == "invalid_output"
    assert explanation_result.candidate_sql is None


def test_provider_factory_switches_between_mock_qwen_and_disabled():
    mock_provider = build_candidate_sql_provider("mock", mock_output="select project_id from project")
    qwen_provider = build_candidate_sql_provider("qwen", qwen_client=FakeQwenClient("select project_id from project"))
    disabled_provider = build_candidate_sql_provider("disabled")

    assert generate_candidate_sql("List projects", _tenant_user(), mock_provider).status == "audit_passed"
    assert isinstance(qwen_provider, QwenCandidateSqlProvider)
    assert isinstance(disabled_provider, DisabledCandidateSqlProvider)

    disabled_result = generate_candidate_sql("List projects", _tenant_user(), disabled_provider)
    assert disabled_result.status == "generation_failed"
    assert "disabled" in disabled_result.rejection_reason
