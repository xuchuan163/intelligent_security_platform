import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field


class HazardCreatePayload(BaseModel):
    description: str = Field(min_length=10)
    hazard_type: str
    hazard_level: Literal["general", "major"]
    subcontractor_id: str
    due_date: dt.date
    location: str | None = None
