from dataclasses import dataclass
from typing import Any, Protocol

from app.core.security import MockUser
from app.services.nl2sql.auditor import audit_sql
from app.services.nl2sql.prompt_builder import build_candidate_sql_prompt
from app.services.nl2sql.schema_context import build_schema_context


class CandidateSqlProvider(Protocol):
    def generate(self, prompt: str) -> str:
        ...


class MockCandidateSqlProvider:
    def __init__(self, output: str | None = None, error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.last_prompt: str | None = None

    def generate(self, prompt: str) -> str:
        self.last_prompt = prompt
        if self.error is not None:
            raise self.error
        return self.output or ""


@dataclass(frozen=True)
class CandidateGenerationResult:
    status: str
    question: str
    candidate_sql: str | None
    sanitized_sql: str | None
    rejection_reason: str | None
    tables_used: list[str]
    fields_used: list[str]
    scope_injected: bool


def _result(
    status: str,
    question: str,
    candidate_sql: str | None = None,
    sanitized_sql: str | None = None,
    rejection_reason: str | None = None,
    tables_used: list[str] | None = None,
    fields_used: list[str] | None = None,
    scope_injected: bool = False,
) -> CandidateGenerationResult:
    return CandidateGenerationResult(
        status=status,
        question=question,
        candidate_sql=candidate_sql,
        sanitized_sql=sanitized_sql,
        rejection_reason=rejection_reason,
        tables_used=tables_used or [],
        fields_used=fields_used or [],
        scope_injected=scope_injected,
    )


def _extract_candidate_sql(raw_output: str) -> tuple[str | None, str | None, str | None]:
    output = raw_output.strip()
    if not output:
        return None, "generation_failed", "LLM returned empty output"

    if output.upper().startswith("CLARIFICATION_REQUIRED"):
        reason = output.split(":", 1)[1].strip() if ":" in output else "clarification required"
        return None, "clarification_required", reason

    if "```" in output or not output.lower().startswith("select"):
        return None, "invalid_output", "LLM output must be plain SQL without Markdown or prose"

    return output, None, None


def generate_candidate_sql(
    question: str,
    current_user: MockUser,
    provider: CandidateSqlProvider,
    metric_aliases: dict[str, list[str]] | None = None,
    clarification_context: dict[str, Any] | None = None,
) -> CandidateGenerationResult:
    schema_context = build_schema_context(metric_aliases=metric_aliases)
    prompt = build_candidate_sql_prompt(
        question=question,
        schema_context=schema_context,
        clarification_context=clarification_context,
    )

    try:
        raw_output = provider.generate(prompt)
    except Exception as exc:
        return _result("generation_failed", question, rejection_reason=str(exc))

    candidate_sql, failure_status, failure_reason = _extract_candidate_sql(raw_output)
    if failure_status is not None:
        return _result(failure_status, question, rejection_reason=failure_reason)

    audit_result = audit_sql(candidate_sql or "", current_user=current_user)
    if not audit_result.allowed:
        return _result(
            "audit_rejected",
            question,
            candidate_sql=candidate_sql,
            rejection_reason=audit_result.reject_reason,
            tables_used=audit_result.tables_used,
            fields_used=audit_result.fields_used,
        )

    return _result(
        "audit_passed",
        question,
        candidate_sql=candidate_sql,
        sanitized_sql=audit_result.sanitized_sql,
        tables_used=audit_result.tables_used,
        fields_used=audit_result.fields_used,
        scope_injected=audit_result.scope_injected,
    )
