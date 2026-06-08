from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.core.config import settings

MilvusStatus = Literal["disabled", "unavailable", "ready"]


class MilvusLike(Protocol):
    def ping(self) -> bool:
        ...

    def list_collections(self) -> list[str]:
        ...

    def close(self) -> None:
        ...


@dataclass(frozen=True)
class MilvusProbeResult:
    status: MilvusStatus
    uri: str
    enabled: bool
    collection_count: int = 0
    detail: str | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "status": self.status,
            "uri": self.uri,
            "enabled": self.enabled,
            "collection_count": self.collection_count,
        }
        if self.detail:
            payload["detail"] = self.detail
        return payload


class MilvusClient:
    def __init__(self, *, uri: str | None = None, timeout: float | None = None) -> None:
        try:
            from pymilvus import MilvusClient as PyMilvusClient
        except ImportError as exc:
            raise RuntimeError("pymilvus package is not installed") from exc

        self.uri = uri or settings.milvus_uri
        self.timeout = timeout if timeout is not None else float(settings.milvus_timeout_seconds)
        self._client = PyMilvusClient(uri=self.uri, timeout=self.timeout)

    def ping(self) -> bool:
        try:
            self._client.get_server_version()
            return True
        except Exception:
            return False

    def list_collections(self) -> list[str]:
        return list(self._client.list_collections())

    def has_collection(self, name: str) -> bool:
        return name in self.list_collections()

    @property
    def sdk(self):
        return self._client

    def describe_collection(self, name: str) -> dict[str, Any]:
        return self._client.describe_collection(name)

    def create_collection(self, *, collection_name: str, schema: Any, index_params: Any) -> None:
        self._client.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )

    def upsert(self, *, collection_name: str, data: list[dict[str, Any]]) -> dict[str, Any]:
        return self._client.upsert(collection_name=collection_name, data=data)

    def search(
        self,
        *,
        collection_name: str,
        data: list[list[float]],
        filter_expr: str,
        limit: int,
        output_fields: list[str],
    ) -> list[list[dict[str, Any]]]:
        return self._client.search(
            collection_name=collection_name,
            data=data,
            filter=filter_expr,
            limit=limit,
            output_fields=output_fields,
            search_params={"metric_type": "COSINE", "params": {}},
        )

    def close(self) -> None:
        self._client.close()


def build_milvus_client() -> MilvusClient:
    if not settings.milvus_enabled:
        raise RuntimeError("Milvus is disabled by configuration")
    client = MilvusClient()
    if not client.ping():
        client.close()
        raise RuntimeError(f"Milvus is unreachable at {settings.milvus_uri}")
    return client


def build_milvus_client_optional() -> MilvusClient | None:
    if not settings.milvus_enabled:
        return None
    try:
        return build_milvus_client()
    except RuntimeError:
        return None


def probe_milvus_status() -> MilvusProbeResult:
    if not settings.milvus_enabled:
        return MilvusProbeResult(
            status="disabled",
            uri=settings.milvus_uri,
            enabled=False,
            detail="MILVUS_ENABLED=false",
        )

    client = build_milvus_client_optional()
    if client is None:
        return MilvusProbeResult(
            status="unavailable",
            uri=settings.milvus_uri,
            enabled=True,
            detail="connection_failed",
        )

    try:
        collections = client.list_collections()
        return MilvusProbeResult(
            status="ready",
            uri=settings.milvus_uri,
            enabled=True,
            collection_count=len(collections),
        )
    finally:
        client.close()
