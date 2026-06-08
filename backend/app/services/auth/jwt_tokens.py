from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.core.config import settings


class TokenValidationError(ValueError):
    pass


def _utcnow() -> datetime:
    return datetime.now(UTC)


def create_access_token(*, user_id: str, tenant_id: str) -> tuple[str, int]:
    expires_minutes = settings.jwt_access_token_expire_minutes
    expires_at = _utcnow() + timedelta(minutes=expires_minutes)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "access",
        "exp": expires_at,
        "iat": _utcnow(),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return token, int(expires_minutes * 60)


def create_refresh_token(*, user_id: str, tenant_id: str) -> str:
    expires_at = _utcnow() + timedelta(days=settings.jwt_refresh_token_expire_days)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "type": "refresh",
        "exp": expires_at,
        "iat": _utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise TokenValidationError("Invalid or expired token") from exc

    token_type = payload.get("type")
    if expected_type and token_type != expected_type:
        raise TokenValidationError(f"Expected token type {expected_type}")
    if not payload.get("sub") or not payload.get("tenant_id"):
        raise TokenValidationError("Token missing required claims")
    return payload
