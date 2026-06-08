from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.core.config import settings
from app.infrastructure.milvus_client import MilvusClient

ACCIDENT_CASES_COLLECTION = "accident_cases"
ACCIDENT_CASES_PRIMARY_FIELD = "case_id"
ACCIDENT_CASES_VECTOR_FIELD = "embedding"
ACCIDENT_CASES_SCALAR_FIELDS = (
    ACCIDENT_CASES_PRIMARY_FIELD,
    "tenant_id",
    "title",
    "summary",
    "tags",
    ACCIDENT_CASES_VECTOR_FIELD,
)

SAFETY_KNOWLEDGE_COLLECTION = "safety_knowledge"
SAFETY_KNOWLEDGE_PRIMARY_FIELD = "chunk_id"
SAFETY_KNOWLEDGE_VECTOR_FIELD = "embedding"
SAFETY_KNOWLEDGE_SCALAR_FIELDS = (
    SAFETY_KNOWLEDGE_PRIMARY_FIELD,
    "tenant_id",
    "source_doc",
    "title",
    "content",
    "tags",
    SAFETY_KNOWLEDGE_VECTOR_FIELD,
)

CollectionAction = Literal["created", "exists"]


@dataclass(frozen=True)
class CollectionEnsureResult:
    collection: str
    action: CollectionAction
    fields: tuple[str, ...]
    embedding_dimension: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "collection": self.collection,
            "action": self.action,
            "fields": list(self.fields),
            "embedding_dimension": self.embedding_dimension,
        }


def build_accident_cases_schema(*, embedding_dimension: int | None = None):
    from pymilvus import DataType, MilvusClient as PyMilvusClient

    dimension = embedding_dimension or settings.milvus_embedding_dimension
    schema = PyMilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field(ACCIDENT_CASES_PRIMARY_FIELD, DataType.VARCHAR, is_primary=True, max_length=64)
    schema.add_field("tenant_id", DataType.VARCHAR, max_length=64)
    schema.add_field("title", DataType.VARCHAR, max_length=256)
    schema.add_field("summary", DataType.VARCHAR, max_length=4096)
    schema.add_field("tags", DataType.VARCHAR, max_length=1024)
    schema.add_field(ACCIDENT_CASES_VECTOR_FIELD, DataType.FLOAT_VECTOR, dim=dimension)
    return schema


def build_accident_cases_index_params(client: MilvusClient):
    index_params = client.sdk.prepare_index_params()
    index_params.add_index(
        field_name=ACCIDENT_CASES_VECTOR_FIELD,
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )
    return index_params


def build_safety_knowledge_schema(*, embedding_dimension: int | None = None):
    from pymilvus import DataType, MilvusClient as PyMilvusClient

    dimension = embedding_dimension or settings.milvus_embedding_dimension
    schema = PyMilvusClient.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field(SAFETY_KNOWLEDGE_PRIMARY_FIELD, DataType.VARCHAR, is_primary=True, max_length=96)
    schema.add_field("tenant_id", DataType.VARCHAR, max_length=64)
    schema.add_field("source_doc", DataType.VARCHAR, max_length=128)
    schema.add_field("title", DataType.VARCHAR, max_length=256)
    schema.add_field("content", DataType.VARCHAR, max_length=4096)
    schema.add_field("tags", DataType.VARCHAR, max_length=1024)
    schema.add_field(SAFETY_KNOWLEDGE_VECTOR_FIELD, DataType.FLOAT_VECTOR, dim=dimension)
    return schema


def build_safety_knowledge_index_params(client: MilvusClient):
    index_params = client.sdk.prepare_index_params()
    index_params.add_index(
        field_name=SAFETY_KNOWLEDGE_VECTOR_FIELD,
        index_type="AUTOINDEX",
        metric_type="COSINE",
    )
    return index_params


def ensure_safety_knowledge_collection(
    client: MilvusClient,
    *,
    embedding_dimension: int | None = None,
) -> CollectionEnsureResult:
    collection_name = settings.milvus_safety_knowledge_collection
    dimension = embedding_dimension or settings.milvus_embedding_dimension

    if client.has_collection(collection_name):
        return CollectionEnsureResult(
            collection=collection_name,
            action="exists",
            fields=SAFETY_KNOWLEDGE_SCALAR_FIELDS,
            embedding_dimension=dimension,
        )

    schema = build_safety_knowledge_schema(embedding_dimension=dimension)
    index_params = build_safety_knowledge_index_params(client)
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )
    return CollectionEnsureResult(
        collection=collection_name,
        action="created",
        fields=SAFETY_KNOWLEDGE_SCALAR_FIELDS,
        embedding_dimension=dimension,
    )


def ensure_rag_collections(client: MilvusClient) -> list[CollectionEnsureResult]:
    return [
        ensure_accident_cases_collection(client),
        ensure_safety_knowledge_collection(client),
    ]


def ensure_accident_cases_collection(
    client: MilvusClient,
    *,
    embedding_dimension: int | None = None,
) -> CollectionEnsureResult:
    collection_name = settings.milvus_accident_cases_collection
    dimension = embedding_dimension or settings.milvus_embedding_dimension

    if client.has_collection(collection_name):
        return CollectionEnsureResult(
            collection=collection_name,
            action="exists",
            fields=ACCIDENT_CASES_SCALAR_FIELDS,
            embedding_dimension=dimension,
        )

    schema = build_accident_cases_schema(embedding_dimension=dimension)
    index_params = build_accident_cases_index_params(client)
    client.create_collection(
        collection_name=collection_name,
        schema=schema,
        index_params=index_params,
    )
    return CollectionEnsureResult(
        collection=collection_name,
        action="created",
        fields=ACCIDENT_CASES_SCALAR_FIELDS,
        embedding_dimension=dimension,
    )
