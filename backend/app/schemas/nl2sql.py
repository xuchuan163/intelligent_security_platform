from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


ProviderName = Literal["disabled", "mock", "qwen"]


class Nl2SqlQueryRequest(BaseModel):
    question: str = Field(default="", max_length=500)
    execute: bool = False
    provider: ProviderName | None = None
    mock_llm_output: str | None = Field(default=None, max_length=5000)
    clarification_id: str | None = Field(default=None, max_length=64)
    clarification_reply: str | None = Field(default=None, max_length=500)
    session_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_question_or_clarification(self) -> "Nl2SqlQueryRequest":
        if self.clarification_id or self.clarification_reply:
            if not self.clarification_id or not self.clarification_reply:
                raise ValueError("clarification_id and clarification_reply must be provided together")
            if len(self.clarification_reply.strip()) < 2:
                raise ValueError("clarification_reply must be at least 2 characters")
            return self
        if len(self.question.strip()) < 2:
            raise ValueError("question must be at least 2 characters")
        return self


class Nl2SqlQueryResponse(BaseModel):
    status: str
    audit_id: str | None
    question: str
    allowed: bool
    sanitized_sql: str | None
    execution_status: str
    row_count: int
    field_count: int
    columns: list[str]
    rows: list[dict[str, Any]]
    execution_error: str | None = None
    rejection_reason: str | None = None
    tables_used: list[str]
    fields_used: list[str]
    scope_injected: bool
    need_human_review: bool = True
    clarification_id: str | None = None
    clarification_prompt: str | None = None
    awaiting_clarification: bool = False
    turn: int = 1
    refined_question: str | None = None
