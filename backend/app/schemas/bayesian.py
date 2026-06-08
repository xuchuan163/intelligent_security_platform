from typing import Literal

from pydantic import BaseModel, Field

ModelLevel = Literal["auto", "L2", "L3"]


class AttributionRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    worker_id: str | None = Field(default=None, max_length=64)
    subcontractor_id: str | None = Field(default=None, max_length=64)
    accident_type: str | None = Field(
        default=None,
        max_length=64,
        description="Optional target accident type label, e.g. 高处坠落",
    )
    model_level: ModelLevel = Field(
        default="auto",
        description="auto: L3 when cases>=200 and CPT exists, otherwise L2",
    )
