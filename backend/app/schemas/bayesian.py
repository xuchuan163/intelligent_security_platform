from pydantic import BaseModel, Field


class AttributionRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    worker_id: str | None = Field(default=None, max_length=64)
    subcontractor_id: str | None = Field(default=None, max_length=64)
    accident_type: str | None = Field(
        default=None,
        max_length=64,
        description="Optional target accident type label, e.g. 高处坠落",
    )
