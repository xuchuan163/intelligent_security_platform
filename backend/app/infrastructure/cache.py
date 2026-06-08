from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.config import settings
from app.infrastructure.redis_client import RedisLike

EMPTY_CACHE_MARKER = "__empty__"
T = TypeVar("T")


def profile_cache_key(profile_type: str, entity_id: str) -> str:
    return f"cache:profile:{profile_type}:{entity_id}"


def nl2sql_cache_key(tenant_id: str, question_hash: str) -> str:
    return f"cache:nl2sql:{tenant_id}:{question_hash}"


def hash_question(question: str) -> str:
    normalized = " ".join(question.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _decode_json(raw: str | bytes | None) -> Any | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _encode_json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str)


def read_profile_cache(
    redis_client: RedisLike | None,
    profile_type: str,
    entity_id: str,
    loader: Callable[[], T | None],
) -> T | None:
    if redis_client is None:
        return loader()

    key = profile_cache_key(profile_type, entity_id)
    cached = _decode_json(redis_client.get(key))
    if cached == EMPTY_CACHE_MARKER:
        return None
    if isinstance(cached, dict):
        return cached  # type: ignore[return-value]

    value = loader()
    if value is None:
        redis_client.setex(key, settings.cache_empty_ttl_seconds, _encode_json(EMPTY_CACHE_MARKER))
    else:
        redis_client.setex(key, settings.cache_profile_ttl_seconds, _encode_json(value))
    return value


def invalidate_profile_cache(
    redis_client: RedisLike | None,
    profile_type: str,
    entity_id: str,
) -> None:
    if redis_client is None:
        return
    redis_client.delete(profile_cache_key(profile_type, entity_id))


def read_nl2sql_cache(redis_client: RedisLike | None, tenant_id: str, question: str) -> dict[str, Any] | None:
    if redis_client is None:
        return None
    key = nl2sql_cache_key(tenant_id, hash_question(question))
    cached = _decode_json(redis_client.get(key))
    if isinstance(cached, dict):
        return cached
    return None


def write_nl2sql_cache(
    redis_client: RedisLike | None,
    tenant_id: str,
    question: str,
    payload: dict[str, Any],
) -> None:
    if redis_client is None:
        return
    key = nl2sql_cache_key(tenant_id, hash_question(question))
    redis_client.setex(key, settings.cache_nl2sql_ttl_seconds, _encode_json(payload))
