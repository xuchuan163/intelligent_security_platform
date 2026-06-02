from typing import Any


def success(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": "SUCCESS", "message": message, "data": data}


def error(code: str, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}
