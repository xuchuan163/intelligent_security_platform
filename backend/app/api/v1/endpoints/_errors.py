from collections.abc import Callable
from typing import TypeVar

from fastapi import HTTPException
from sqlalchemy.exc import SQLAlchemyError

T = TypeVar("T")


def db_guard(fn: Callable[[], T]) -> T:
    try:
        return fn()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc.__class__.__name__}") from exc
