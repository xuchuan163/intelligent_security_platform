from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.core.config import settings

RedisStatus = Literal["disabled", "unavailable", "ready"]


class RedisLike(Protocol):
    def get(self, key: str) -> str | bytes | None:
        ...

    def setex(self, key: str, ttl: int, value: str) -> object:
        ...

    def delete(self, key: str) -> object:
        ...

    def ping(self) -> bool:
        ...


@dataclass(frozen=True)
class RedisProbeResult:
    status: RedisStatus
    url: str
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "url": self.url,
        }
        if self.detail:
            payload["detail"] = self.detail
        return payload


def build_redis_client() -> RedisLike:
    try:
        from redis import Redis
    except ImportError as exc:
        raise RuntimeError("Redis client package is not installed") from exc

    return Redis.from_url(settings.redis_url, decode_responses=True)


def build_redis_client_optional() -> RedisLike | None:
    try:
        return build_redis_client()
    except RuntimeError:
        return None


def probe_redis_status() -> RedisProbeResult:
    client = build_redis_client_optional()
    if client is None:
        return RedisProbeResult(
            status="unavailable",
            url=settings.redis_url,
            detail="connection_failed_or_package_missing",
        )
    try:
        if client.ping():
            return RedisProbeResult(status="ready", url=settings.redis_url)
        return RedisProbeResult(
            status="unavailable",
            url=settings.redis_url,
            detail="ping_failed",
        )
    except Exception as exc:
        return RedisProbeResult(
            status="unavailable",
            url=settings.redis_url,
            detail=str(exc),
        )
