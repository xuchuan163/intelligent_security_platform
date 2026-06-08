import datetime
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_CODE_BY_STATUS = {
    400: "40001",
    401: "40101",
    403: "40301",
    404: "40401",
    409: "40901",
    422: "42201",
    500: "50001",
    501: "50101",
    503: "50301",
}

CHINA_TZ = datetime.timezone(datetime.timedelta(hours=8))


def request_id_for(request: Request) -> str:
    return request.headers.get("X-Request-Id") or str(uuid.uuid4())


def error_payload(status_code: int, message: str, request_id: str, data: Any = None) -> dict[str, Any]:
    return {
        "code": ERROR_CODE_BY_STATUS.get(status_code, "50001"),
        "message": message,
        "request_id": request_id,
        "data": data,
        "timestamp": datetime.datetime.now(CHINA_TZ).isoformat(),
    }


def error_response(status_code: int, message: str, request_id: str, data: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_payload(status_code, message, request_id, data),
        headers={"X-Request-Id": request_id},
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        message = str(exc.detail) if exc.detail else "Request failed"
        return error_response(exc.status_code, message, request_id_for(request))

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(
            422,
            "Validation error",
            request_id_for(request),
            {"errors": jsonable_encoder(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        return error_response(500, exc.__class__.__name__, request_id_for(request))
