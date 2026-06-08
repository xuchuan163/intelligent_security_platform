from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class AgentAskRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1000)
    context: dict[str, Any] | None = None
    session_id: str | None = Field(default=None, max_length=64)
    execution_mode: Literal["route_only", "execute_preview", "plan_only", "dry_run", "controlled_execute"] = "route_only"


class AgentPromptActivateRequest(BaseModel):
    prompt_version: str = Field(min_length=2, max_length=32)


class AgentApprovalDecisionRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=500)


class AgentFeedbackCreateRequest(BaseModel):
    task_id: str = Field(min_length=2, max_length=64)
    agent_name: str = Field(min_length=2, max_length=64)
    feedback_type: Literal["thumb", "rating", "correction", "adoption"]
    rating: int | None = Field(default=None, ge=-1, le=5)
    feedback_reason: str | None = Field(default=None, max_length=255)
    original_output: dict[str, Any] | None = None
    corrected_output: dict[str, Any] | None = None
    correction_text: str | None = Field(default=None, max_length=2000)
    related_work_order_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_feedback_shape(self) -> "AgentFeedbackCreateRequest":
        if self.feedback_type == "thumb" and self.rating not in {1, -1}:
            raise ValueError("thumb feedback requires rating 1 or -1")
        if self.feedback_type == "rating" and (self.rating is None or self.rating < 1 or self.rating > 5):
            raise ValueError("rating feedback requires rating between 1 and 5")
        if self.feedback_type == "correction" and not self.correction_text and not self.corrected_output:
            raise ValueError("correction feedback requires correction_text or corrected_output")
        return self
