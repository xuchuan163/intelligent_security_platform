from pydantic import BaseModel
from typing import Any


class APIResponse(BaseModel):
    code: str = "SUCCESS"
    message: str = "ok"
    data: Any = None
