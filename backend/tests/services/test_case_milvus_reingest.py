"""Milvus re-ingest hook tests (Phase 4-B.6)."""

from __future__ import annotations

import datetime as dt
import textwrap
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base
from app.services.cases.import_cases import ImportCaseError, import_accident_cases_from_csv
from app.services.cases.milvus_reingest import trigger_accident_case_milvus_reingest
from app.services.rag.embedding import MockEmbeddingProvider


class _FakeMilvusSdk:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.upserted: dict[str, list[dict]] = {}

    def prepare_index_params(self):
        return _FakeIndexParams()

    def create_collection(self, *, collection_name: str, schema, index_params) -> None:
        self.collections.add(collection_name)

    def upsert(self, *, collection_name: str, data: list[dict]) -> dict:
        self.upserted.setdefault(collection_name, []).extend(data)
        return {"upsert_count": len(data)}


class _FakeIndexParams:
    def add_index(self, **kwargs) -> None:
        return None


class _FakeMilvusClient:
    def __init__(self) -> None:
        self.sdk = _FakeMilvusSdk()
        self._collections = self.sdk.collections

    def has_collection(self, name: str) -> bool:
        return name in self._collections

    def list_collections(self) -> list[str]:
        return sorted(self._collections)

    def create_collection(self, *, collection_name: str, schema, index_params) -> None:
        self.sdk.create_collection(
            collection_name=collection_name,
            schema=schema,
            index_params=index_params,
        )
        self._collections.add(collection_name)

    def upsert(self, *, collection_name: str, data: list[dict]) -> dict:
        return self.sdk.upsert(collection_name=collection_name, data=data)

    def close(self) -> None:
        return None


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _seed_case(db, *, case_id: str = "AC-REINGEST-001", tenant_id: str = "CSCEC") -> None:
    db.add(
        AccidentCaseLibrary(
            accident_case_id=case_id,
            tenant_id=tenant_id,
            accident_type="高处坠落",
            severity="一般事故",
            operation_scene="临边作业",
            direct_cause="防护缺失",
            indirect_cause="交底不足",
            rectification_measures="恢复防护",
            tags=["高处作业"],
            status="active",
            created_at=dt.datetime(2026, 6, 1, 9, 0, 0),
        )
    )
    db.commit()


def test_trigger_skipped_when_milvus_disabled(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", False)
    db = _session()
    _seed_case(db)

    result = trigger_accident_case_milvus_reingest(db, tenant_id="CSCEC")

    assert result["status"] == "skipped"
    assert result["reason"] == "milvus_disabled"
    assert result["upserted"] == 0


def test_trigger_ingests_tenant_cases_with_injected_client(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", True)
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    monkeypatch.setattr(settings, "milvus_embedding_dimension", 8)

    db = _session()
    _seed_case(db)
    client = _FakeMilvusClient()
    embedder = MockEmbeddingProvider(dimension=8)

    result = trigger_accident_case_milvus_reingest(
        db,
        tenant_id="CSCEC",
        accident_case_ids=["AC-REINGEST-001"],
        milvus_client=client,
        embedder=embedder,
    )

    assert result["status"] == "ingested"
    assert result["upserted"] == 1
    assert client.has_collection("accident_cases")
    assert len(client.sdk.upserted["accident_cases"]) == 1

    row = db.query(AccidentCaseLibrary).filter_by(accident_case_id="AC-REINGEST-001").one()
    assert row.embedding_version is not None
    assert row.embedding_version.startswith("rag-mock-")


def test_import_cases_triggers_reingest_hook_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "milvus_enabled", True)
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    monkeypatch.setattr(settings, "milvus_embedding_dimension", 8)
    monkeypatch.setattr(settings, "embedding_provider", "mock")

    client = _FakeMilvusClient()
    monkeypatch.setattr(
        "app.services.cases.milvus_reingest.build_milvus_client_optional",
        lambda: client,
    )

    csv_path = tmp_path / "cases.csv"
    csv_path.write_text(
        textwrap.dedent(
            """
            accident_case_id,tenant_id,accident_type,severity
            AC-IMPORT-201,TENANT-A,机械伤害,一般事故
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    db = _session()

    result = import_accident_cases_from_csv(
        db,
        csv_path,
        reingest_milvus=True,
    )

    assert result.created == 1
    assert result.milvus_reingest is not None
    assert result.milvus_reingest["status"] == "ingested"
    assert result.milvus_reingest["upserted"] == 1
    row = db.query(AccidentCaseLibrary).filter_by(accident_case_id="AC-IMPORT-201").one()
    assert row.embedding_version is not None


def test_import_cases_rejects_multi_tenant_reingest_batch(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "milvus_enabled", True)
    csv_path = tmp_path / "cases.csv"
    csv_path.write_text(
        textwrap.dedent(
            """
            accident_case_id,tenant_id,accident_type,severity
            AC-IMPORT-301,TENANT-A,机械伤害,一般事故
            AC-IMPORT-302,TENANT-B,触电,一般事故
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    db = _session()

    try:
        import_accident_cases_from_csv(db, csv_path, reingest_milvus=True)
    except ImportCaseError as exc:
        assert "single tenant_id" in str(exc)
    else:
        raise AssertionError("expected ImportCaseError for multi-tenant reingest")
