from typing import Any

from pydantic import BaseModel


class MetricCatalogItem(BaseModel):
    metric_code: str
    metric_name: str
    business_definition: str | None = None
    statistical_period: str | None = None
    permission_level: str | None = None
    metric_version: str
    status: str


class MetricDetail(MetricCatalogItem):
    calculation_formula: str | None = None
    dimensions: Any | None = None
    source_tables: Any | None = None
    source_fields: Any | None = None
    filters: Any | None = None
    aliases: Any | None = None
    owner_department: str | None = None


class MetricCatalogPage(BaseModel):
    page_no: int
    page_size: int
    total: int
    items: list[MetricCatalogItem]


class MetricValidateRequest(BaseModel):
    metric_codes: list[str]
