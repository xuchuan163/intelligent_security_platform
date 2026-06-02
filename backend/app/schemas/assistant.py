from pydantic import BaseModel
from typing import Any


class AssistantChatRequest(BaseModel):
    message: str
    context: dict[str, Any] | None = None


class AssistantProjectExplainRequest(BaseModel):
    project_id: str
    facts: dict[str, Any] | None = None
