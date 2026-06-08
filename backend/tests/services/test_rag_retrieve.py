import datetime as dt

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.models import AccidentCaseLibrary
from app.infrastructure.database.session import Base
from app.services.rag.embedding import MockEmbeddingProvider
from app.services.rag.retrieve import (
    build_tenant_filter,
    distance_to_score,
    retrieve_rag_hits,
    retrieve_with_fallback,
    vector_search_collection,
)


class _FakeMilvusSdk:
    def __init__(self, hits: list[dict] | None = None) -> None:
        self.hits = hits or []
        self.last_filter: str | None = None
        self.last_limit: int | None = None

    def search(self, *, collection_name, data, filter, limit, output_fields, search_params):
        self.last_filter = filter
        self.last_limit = limit
        return [self.hits]


class _FakeMilvusClient:
    def __init__(self, *, collections: set[str], hits: list[dict] | None = None) -> None:
        self._collections = collections
        self.sdk = _FakeMilvusSdk(hits=hits)

    def ping(self) -> bool:
        return True

    def has_collection(self, name: str) -> bool:
        return name in self._collections

    def list_collections(self) -> list[str]:
        return sorted(self._collections)

    def search(self, *, collection_name, data, filter_expr, limit, output_fields):
        return self.sdk.search(
            collection_name=collection_name,
            data=data,
            filter=filter_expr,
            limit=limit,
            output_fields=output_fields,
            search_params={"metric_type": "COSINE", "params": {}},
        )

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


def _seed_case(db, *, tenant_id: str, accident_type: str) -> None:
    db.add(
        AccidentCaseLibrary(
            accident_case_id=f"AC-{tenant_id}-{accident_type}",
            tenant_id=tenant_id,
            accident_type=accident_type,
            severity="一般事故",
            direct_cause="原因说明",
            indirect_cause="间接原因",
            rectification_measures="整改措施",
            tags=["测试"],
            status="active",
            created_at=dt.datetime(2026, 6, 1, 9, 0, 0),
        )
    )
    db.commit()


def test_build_tenant_filter_escapes_quotes():
    assert build_tenant_filter('CSCEC') == 'tenant_id == "CSCEC"'
    assert build_tenant_filter('TEN"ANT') == 'tenant_id == "TEN\\"ANT"'


def test_distance_to_score_maps_cosine_distance():
    assert distance_to_score(0.0) == 1.0
    assert distance_to_score(0.4) == 0.6


def test_vector_search_collection_applies_tenant_filter_and_score_threshold(monkeypatch):
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    hits = [
        {
            "distance": 0.1,
            "entity": {
                "case_id": "AC-001",
                "tenant_id": "CSCEC",
                "title": "高处坠落",
                "summary": "摘要",
                "tags": "[]",
            },
        },
        {
            "distance": 0.9,
            "entity": {
                "case_id": "AC-002",
                "tenant_id": "CSCEC",
                "title": "低相关",
                "summary": "摘要",
                "tags": "[]",
            },
        },
    ]
    client = _FakeMilvusClient(collections={"accident_cases"}, hits=hits)
    embedder = MockEmbeddingProvider(dimension=8)

    result = vector_search_collection(
        client,
        collection_name="accident_cases",
        query_vector=embedder.embed_texts(["高处作业"])[0],
        tenant_id="CSCEC",
        top_k=3,
        score_threshold=0.5,
        output_fields=["case_id", "tenant_id", "title", "summary", "tags"],
        id_field="case_id",
        content_field="summary",
    )

    assert client.sdk.last_filter == 'tenant_id == "CSCEC"'
    assert client.sdk.last_limit == 3
    assert len(result) == 1
    assert result[0].record_id == "AC-001"
    assert result[0].score == 0.9


def test_retrieve_rag_hits_merges_collections(monkeypatch):
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    monkeypatch.setattr(settings, "milvus_safety_knowledge_collection", "safety_knowledge")
    monkeypatch.setattr(settings, "rag_top_k", 2)
    monkeypatch.setattr(settings, "rag_score_threshold", 0.1)
    monkeypatch.setattr(settings, "milvus_embedding_dimension", 8)

    class _DualCollectionClient(_FakeMilvusClient):
        def search(self, *, collection_name, data, filter_expr, limit, output_fields):
            if collection_name == "accident_cases":
                return [[{
                    "distance": 0.2,
                    "entity": {
                        "case_id": "AC-001",
                        "tenant_id": "CSCEC",
                        "title": "案例",
                        "summary": "案例摘要",
                        "tags": "[]",
                    },
                }]]
            return [[{
                "distance": 0.1,
                "entity": {
                    "chunk_id": "SK-001",
                    "tenant_id": "CSCEC",
                    "source_doc": "demo",
                    "title": "制度",
                    "content": "制度内容",
                    "tags": "[]",
                },
            }]]

    client = _DualCollectionClient(collections={"accident_cases", "safety_knowledge"})
    embedder = MockEmbeddingProvider(dimension=8)

    hits = retrieve_rag_hits(
        client,
        query="临边防护",
        tenant_id="CSCEC",
        embedder=embedder,
    )

    assert len(hits) == 2
    assert hits[0].record_id == "SK-001"


def test_retrieve_with_fallback_uses_mysql_when_milvus_disabled(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", False)
    monkeypatch.setattr(settings, "rag_top_k", 3)
    db = _session()
    _seed_case(db, tenant_id="CSCEC", accident_type="触电")

    result = retrieve_with_fallback(db, query="触电", tenant_id="CSCEC")

    assert result["mode"] == "mysql_keyword"
    assert result["total"] == 1
    assert result["items"][0]["record_id"] == "AC-CSCEC-触电"


def test_retrieve_with_fallback_uses_milvus_when_hits_exist(monkeypatch):
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    monkeypatch.setattr(settings, "milvus_safety_knowledge_collection", "safety_knowledge")
    monkeypatch.setattr(settings, "rag_top_k", 3)
    monkeypatch.setattr(settings, "rag_score_threshold", 0.1)
    monkeypatch.setattr(settings, "milvus_embedding_dimension", 8)

    client = _FakeMilvusClient(
        collections={"accident_cases", "safety_knowledge"},
        hits=[{
            "distance": 0.15,
            "entity": {
                "case_id": "AC-001",
                "tenant_id": "CSCEC",
                "title": "高处坠落",
                "summary": "摘要",
                "tags": "[]",
            },
        }],
    )
    db = _session()
    embedder = MockEmbeddingProvider(dimension=8)

    result = retrieve_with_fallback(
        db,
        query="高处坠落",
        tenant_id="CSCEC",
        milvus_client=client,
        embedder=embedder,
    )

    assert result["mode"] == "milvus"
    assert result["total"] >= 1
    assert any(item["collection"] == "accident_cases" for item in result["items"])
