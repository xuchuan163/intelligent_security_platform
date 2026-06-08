from app.core.config import settings
from app.infrastructure.milvus_client import (
    MilvusClient,
    build_milvus_client_optional,
    probe_milvus_status,
)


class _FakeMilvusClient:
    def __init__(self, *, ping_ok: bool = True, collections: list[str] | None = None) -> None:
        self.ping_ok = ping_ok
        self.collections = collections or []
        self.closed = False

    def ping(self) -> bool:
        return self.ping_ok

    def list_collections(self) -> list[str]:
        return self.collections

    def close(self) -> None:
        self.closed = True


def test_build_milvus_client_optional_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", False)

    assert build_milvus_client_optional() is None


def test_build_milvus_client_optional_returns_none_when_unreachable(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", True)

    def _raise_runtime_error() -> MilvusClient:
        raise RuntimeError("unreachable")

    monkeypatch.setattr(
        "app.infrastructure.milvus_client.build_milvus_client",
        _raise_runtime_error,
    )

    assert build_milvus_client_optional() is None


def test_probe_milvus_status_disabled(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", False)
    monkeypatch.setattr(settings, "milvus_uri", "http://127.0.0.1:29530")

    result = probe_milvus_status()

    assert result.status == "disabled"
    assert result.enabled is False


def test_probe_milvus_status_ready(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", True)
    monkeypatch.setattr(
        "app.infrastructure.milvus_client.build_milvus_client_optional",
        lambda: _FakeMilvusClient(collections=["accident_cases"]),
    )

    result = probe_milvus_status()

    assert result.status == "ready"
    assert result.collection_count == 1


def test_probe_milvus_status_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", True)
    monkeypatch.setattr("app.infrastructure.milvus_client.build_milvus_client_optional", lambda: None)

    result = probe_milvus_status()

    assert result.status == "unavailable"
    assert result.enabled is True
