from pydantic import BaseModel, Field


class WeightConfigVersionItem(BaseModel):
    config_key: str
    version: str
    effective_from: str
    source_path: str


class WeightConfigVersionsResponse(BaseModel):
    items: list[dict] = Field(default_factory=list)
