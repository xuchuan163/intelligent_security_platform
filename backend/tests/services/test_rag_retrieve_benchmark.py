"""RAG retrieval benchmark (Task 3-C.9): rag_retrieval_30.jsonl hit-rate gate."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.infrastructure.database.session import Base
from app.services.cases.seed_cases import seed_accident_cases
from app.services.rag.benchmark import (
    DEFAULT_DATASET_PATH,
    DEFAULT_KNOWLEDGE_DIR,
    load_rag_retrieval_cases,
    run_rag_retrieval_benchmark,
)

REQUIRED_FIELDS = {"case_id", "category", "tenant_id", "query", "expected_record_ids", "top_k"}
MIN_HIT_RATE = 0.8


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def test_rag_retrieval_dataset_exists_and_has_at_least_thirty_cases():
    assert DEFAULT_DATASET_PATH.is_file()
    cases = load_rag_retrieval_cases()
    assert len(cases) >= 30


def test_rag_retrieval_dataset_schema():
    cases = load_rag_retrieval_cases()
    categories = {"accident_case", "safety_knowledge"}
    for case in cases:
        assert REQUIRED_FIELDS.issubset(case.keys())
        assert case["category"] in categories
        assert isinstance(case["expected_record_ids"], list)
        assert len(case["expected_record_ids"]) >= 1
        assert case["top_k"] >= 1


def test_rag_retrieval_benchmark_meets_hit_rate_without_milvus(monkeypatch):
    monkeypatch.setattr(settings, "milvus_enabled", False)
    db = _session()
    seed_accident_cases(db)

    cases = load_rag_retrieval_cases()
    report = run_rag_retrieval_benchmark(
        db,
        cases,
        milvus_client=None,
        knowledge_dir=DEFAULT_KNOWLEDGE_DIR,
    )

    if report["failed"]:
        failures = [
            {
                "case_id": item["case"]["case_id"],
                "errors": item["errors"],
                "returned": item["returned_record_ids"],
            }
            for item in report["evaluations"]
            if not item["passed"]
        ]
        pytest.fail(
            f"top_k_hit_rate={report['top_k_hit_rate']} below {MIN_HIT_RATE}; "
            f"failures={failures}"
        )

    assert report["top_k_hit_rate"] >= MIN_HIT_RATE
    assert report["total"] == len(cases)
    assert report["passed"] + report["failed"] == report["total"]
