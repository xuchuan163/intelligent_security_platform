from app.core.config import settings
from app.services.rag.collections import (
    ACCIDENT_CASES_SCALAR_FIELDS,
    ACCIDENT_CASES_VECTOR_FIELD,
    SAFETY_KNOWLEDGE_SCALAR_FIELDS,
    SAFETY_KNOWLEDGE_VECTOR_FIELD,
    build_accident_cases_schema,
    build_safety_knowledge_schema,
    ensure_accident_cases_collection,
    ensure_safety_knowledge_collection,
)


class _FakeMilvusSdk:
    def __init__(self) -> None:
        self.collections: set[str] = set()
        self.created: list[str] = []

    def prepare_index_params(self):
        return _FakeIndexParams()

    def create_collection(self, *, collection_name: str, schema, index_params) -> None:
        self.collections.add(collection_name)
        self.created.append(collection_name)


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


def test_accident_cases_schema_contains_required_fields():
    schema = build_accident_cases_schema(embedding_dimension=8)
    schema_dict = schema.to_dict()
    field_names = {field["name"] for field in schema_dict["fields"]}

    assert field_names == set(ACCIDENT_CASES_SCALAR_FIELDS)
    embedding_field = next(
        field for field in schema_dict["fields"] if field["name"] == ACCIDENT_CASES_VECTOR_FIELD
    )
    assert embedding_field["params"]["dim"] == 8


def test_ensure_accident_cases_collection_creates_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    client = _FakeMilvusClient()

    result = ensure_accident_cases_collection(client, embedding_dimension=16)

    assert result.action == "created"
    assert result.collection == "accident_cases"
    assert result.embedding_dimension == 16
    assert client.has_collection("accident_cases")


def test_safety_knowledge_schema_contains_required_fields():
    schema = build_safety_knowledge_schema(embedding_dimension=8)
    schema_dict = schema.to_dict()
    field_names = {field["name"] for field in schema_dict["fields"]}

    assert field_names == set(SAFETY_KNOWLEDGE_SCALAR_FIELDS)
    embedding_field = next(
        field for field in schema_dict["fields"] if field["name"] == SAFETY_KNOWLEDGE_VECTOR_FIELD
    )
    assert embedding_field["params"]["dim"] == 8


def test_ensure_safety_knowledge_collection_creates_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "milvus_safety_knowledge_collection", "safety_knowledge")
    client = _FakeMilvusClient()

    result = ensure_safety_knowledge_collection(client, embedding_dimension=16)

    assert result.action == "created"
    assert result.collection == "safety_knowledge"
    assert client.has_collection("safety_knowledge")


def test_ensure_accident_cases_collection_is_idempotent(monkeypatch):
    monkeypatch.setattr(settings, "milvus_accident_cases_collection", "accident_cases")
    client = _FakeMilvusClient()
    client._collections.add("accident_cases")

    result = ensure_accident_cases_collection(client)

    assert result.action == "exists"
    assert len(client.sdk.created) == 0
