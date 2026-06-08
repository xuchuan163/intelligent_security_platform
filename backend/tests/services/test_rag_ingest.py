import datetime as dt
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base
from app.services.rag.embedding import MockEmbeddingProvider
from app.services.rag.ingest import (
    build_accident_case_records,
    build_safety_knowledge_records,
    ingest_rag_corpus,
)
from app.services.rag.chunking import KnowledgeChunkDraft


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


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _seed_accident_case(db) -> None:
    db.add(
        AccidentCaseLibrary(
            accident_case_id="AC-INGEST-001",
            tenant_id="CSCEC",
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


def test_build_accident_case_records_contains_embedding():
    db = _session()
    _seed_accident_case(db)
    row = db.query(AccidentCaseLibrary).one()
    embedder = MockEmbeddingProvider(dimension=8)

    records = build_accident_case_records([row], embedder=embedder)

    assert len(records) == 1
    assert records[0]["case_id"] == "AC-INGEST-001"
    assert len(records[0]["embedding"]) == 8


def test_build_safety_knowledge_records_contains_embedding():
    chunks = [
        KnowledgeChunkDraft(
            chunk_id="SK-CSCEC-demo-001",
            tenant_id="CSCEC",
            source_doc="demo",
            title="第一节",
            content="制度内容",
            tags=["测试"],
        )
    ]
    embedder = MockEmbeddingProvider(dimension=8)

    records = build_safety_knowledge_records(chunks, embedder=embedder)

    assert records[0]["chunk_id"] == "SK-CSCEC-demo-001"
    assert len(records[0]["embedding"]) == 8


def test_ingest_rag_corpus_upserts_both_collections(monkeypatch):
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    monkeypatch.setattr(settings, "milvus_safety_knowledge_collection", "safety_knowledge")
    monkeypatch.setattr(settings, "milvus_embedding_dimension", 8)
    monkeypatch.setattr(settings, "rag_default_tenant_id", "CSCEC")

    db = _session()
    _seed_accident_case(db)
    client = _FakeMilvusClient()
    knowledge_dir = Path(__file__).resolve().parents[3] / "config" / "knowledge"
    embedder = MockEmbeddingProvider(dimension=8)

    result = ingest_rag_corpus(
        db,
        client,
        knowledge_dir=knowledge_dir,
        tenant_id="CSCEC",
        embedder=embedder,
    )

    assert result["embedding_provider"] == "mock"
    assert client.has_collection("accident_cases")
    assert client.has_collection("safety_knowledge")
    assert len(client.sdk.upserted["accident_cases"]) == 1
    assert len(client.sdk.upserted["safety_knowledge"]) >= 10
