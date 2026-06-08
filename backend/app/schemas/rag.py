from pydantic import BaseModel, Field


class RagSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    top_k: int | None = Field(None, ge=1, le=20)
    score_threshold: float | None = Field(None, ge=0.0, le=1.0)
