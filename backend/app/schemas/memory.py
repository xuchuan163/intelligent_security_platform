from typing import Any, Literal

from pydantic import BaseModel, Field


class MemoryMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=1)
    metadata: dict[str, Any] | None = None


class MemorySessionUpsertRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: MemoryMessage
    context: dict[str, Any] | None = None
    summary: str | None = None
