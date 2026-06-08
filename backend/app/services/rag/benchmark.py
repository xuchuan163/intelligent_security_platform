from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.infrastructure.milvus_client import MilvusClient
from app.services.rag.chunking import KnowledgeChunkDraft, load_knowledge_chunks
from app.services.rag.embedding import EmbeddingProvider, build_embedding_provider
from app.services.rag.keyword_search import keyword_search_accident_cases
from app.services.rag.retrieve import retrieve_with_fallback

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_PATH = _BACKEND_ROOT / "tests" / "datasets" / "rag_retrieval_30.jsonl"
DEFAULT_KNOWLEDGE_DIR = _BACKEND_ROOT.parent / "config" / "knowledge"


def load_rag_retrieval_cases(path: str | Path = DEFAULT_DATASET_PATH) -> list[dict[str, Any]]:
    dataset_path = Path(path)
    return [
        json.loads(line)
        for line in dataset_path.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]


def _rate(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 1.0
    return round(numerator / denominator, 4)


def _keyword_match(text: str, query: str) -> bool:
    normalized_query = query.strip().lower()
    if not normalized_query:
        return False
    haystack = text.lower()
    tokens = [token for token in normalized_query.replace("，", " ").split() if token]
    if not tokens:
        return normalized_query in haystack
    return any(token in haystack for token in tokens)


def keyword_search_knowledge_chunks(
    knowledge_dir: Path,
    *,
    tenant_id: str,
    query: str,
    limit: int = 3,
) -> list[dict[str, Any]]:
    chunks = load_knowledge_chunks(knowledge_dir, tenant_id=tenant_id)
    matched: list[KnowledgeChunkDraft] = []
    for chunk in chunks:
        searchable = f"{chunk.title}\n{chunk.content}\n{' '.join(chunk.tags)}"
        if _keyword_match(searchable, query):
            matched.append(chunk)

    return [
        {
            "collection": "safety_knowledge",
            "record_id": chunk.chunk_id,
            "tenant_id": chunk.tenant_id,
            "title": chunk.title,
            "content": chunk.content,
            "score": 0.5,
            "source_doc": chunk.source_doc,
            "tags": json.dumps(chunk.tags, ensure_ascii=False),
        }
        for chunk in matched[:limit]
    ]


def evaluate_rag_retrieval_case(
    db: Session,
    case: dict[str, Any],
    *,
    embedder: EmbeddingProvider | None = None,
    milvus_client: MilvusClient | None = None,
    knowledge_dir: Path | None = None,
) -> dict[str, Any]:
    top_k = int(case.get("top_k") or settings.rag_top_k)
    tenant_id = case["tenant_id"]
    query = case["query"]
    expected_ids = set(case["expected_record_ids"])
    errors: list[str] = []

    if milvus_client is None:
        if case["category"] == "safety_knowledge":
            items = keyword_search_knowledge_chunks(
                knowledge_dir or DEFAULT_KNOWLEDGE_DIR,
                tenant_id=tenant_id,
                query=query,
                limit=top_k,
            )
            mode = "in_memory_keyword"
        else:
            rows = keyword_search_accident_cases(
                db, tenant_id=tenant_id, query=query, limit=top_k
            )
            items = [
                {
                    "collection": "accident_cases",
                    "record_id": row["accident_case_id"],
                    "tenant_id": row["tenant_id"],
                    "title": row.get("accident_type") or row["accident_case_id"],
                    "content": row.get("direct_cause") or "",
                    "score": 0.5,
                }
                for row in rows
            ]
            mode = "mysql_keyword"
    else:
        result = retrieve_with_fallback(
            db,
            query=query,
            tenant_id=tenant_id,
            top_k=top_k,
            milvus_client=milvus_client,
            embedder=embedder,
        )
        items = result.get("items", [])
        mode = result.get("mode", "unknown")

    returned_ids = [str(item.get("record_id", "")) for item in items[:top_k]]
    hit = any(record_id in expected_ids for record_id in returned_ids)
    if not hit:
        errors.append(
            f"expected one of {sorted(expected_ids)} in top_{top_k}, got {returned_ids}"
        )

    return {
        "case": case,
        "passed": hit,
        "errors": errors,
        "mode": mode,
        "returned_record_ids": returned_ids,
    }


def run_rag_retrieval_benchmark(
    db: Session,
    cases: list[dict[str, Any]],
    *,
    embedder: EmbeddingProvider | None = None,
    milvus_client: MilvusClient | None = None,
    knowledge_dir: Path | None = None,
) -> dict[str, Any]:
    embedder = embedder or build_embedding_provider()
    category_stats: dict[str, dict[str, int]] = {}
    evaluations: list[dict[str, Any]] = []

    for case in cases:
        evaluation = evaluate_rag_retrieval_case(
            db,
            case,
            embedder=embedder,
            milvus_client=milvus_client,
            knowledge_dir=knowledge_dir,
        )
        evaluations.append(evaluation)
        category = case["category"]
        bucket = category_stats.setdefault(category, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        if evaluation["passed"]:
            bucket["passed"] += 1
        else:
            bucket["failed"] += 1

    passed = sum(1 for item in evaluations if item["passed"])
    failed = len(evaluations) - passed
    return {
        "total": len(evaluations),
        "passed": passed,
        "failed": failed,
        "top_k_hit_rate": _rate(passed, len(evaluations)),
        "category_breakdown": category_stats,
        "evaluations": evaluations,
    }
