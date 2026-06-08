import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import DataScope, MockUser
from app.infrastructure.database.session import Base
from app.services.memory.benchmark import load_memory_context_cases, run_memory_context_benchmark
from app.services.memory.context_resolver import (
    extract_explicit_entities,
    merge_session_context,
    resolve_follow_up_context,
)
from app.services.memory.service import append_session_memory, get_session_memory


DATASET_PATH = Path(__file__).resolve().parents[1] / "datasets" / "memory_context_55.jsonl"


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    def get(self, key: str) -> str | None:
        return self.values.get(key)


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def _user() -> MockUser:
    return MockUser(
        user_id="u-mem-bench-001",
        user_name="Memory Benchmark User",
        tenant_id="TENANT-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
    )


def test_memory_context_dataset_has_required_size_schema_and_categories():
    cases = [
        json.loads(line)
        for line in DATASET_PATH.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    required_keys = {
        "case_id",
        "category",
        "flow",
        "session_id",
        "turns",
        "expected_resolved_context",
        "difficulty",
    }
    categories = {case["category"] for case in cases}

    assert len(cases) >= 50
    assert all(required_keys <= set(case) for case in cases)
    assert len({case["case_id"] for case in cases}) == len(cases)
    assert {
        "project_reference",
        "hazard_reference",
        "work_order_reference",
        "metric_reference",
        "rule_reference",
        "multi_entity",
        "pronoun_follow_up",
        "nl2sql_clarification",
        "context_sanitization",
    } <= categories


def test_merge_session_context_preserves_prior_entities_when_follow_up_is_empty():
    merged = merge_session_context(
        {"project_id": "P001", "risk_level": "high"},
        {"intent": "follow_up"},
    )
    assert merged == {"project_id": "P001", "risk_level": "high", "intent": "follow_up"}


def test_extract_explicit_entities_from_follow_up_message():
    found = extract_explicit_entities("请继续分析 P002 和 H003 的 SR-PROJ-001 触发")
    assert found == {
        "project_id": "P002",
        "hazard_id": "H003",
        "rule_id": "SR-PROJ-001",
    }


def test_append_session_memory_merges_context_across_turns():
    engine, db = _session()
    redis = FakeRedis()
    try:
        append_session_memory(
            db,
            redis,
            current_user=_user(),
            session_id="MERGE-001",
            message={"role": "user", "content": "查看 P001"},
            context={"project_id": "P001"},
        )
        append_session_memory(
            db,
            redis,
            current_user=_user(),
            session_id="MERGE-001",
            message={"role": "user", "content": "它的风险驱动因素是什么？"},
            context={},
        )
        memory = get_session_memory(db, redis, current_user=_user(), session_id="MERGE-001")
        assert memory is not None
        resolved = resolve_follow_up_context(memory, follow_up_message="它的风险驱动因素是什么？")
        assert resolved["project_id"] == "P001"
    finally:
        db.close()
        engine.dispose()


def test_memory_context_benchmark_meets_ninety_percent_hit_rate():
    engine, db = _session()
    redis = FakeRedis()
    try:
        cases = load_memory_context_cases(DATASET_PATH)
        report = run_memory_context_benchmark(
            cases,
            db=db,
            redis_client=redis,
            current_user=_user(),
        )

        assert report["total_cases"] >= 50
        assert report["failed_cases"] == 0
        assert report["context_hit_rate"] >= 0.9
        assert report["failures"] == []
        assert report["category_summary"]["project_reference"]["total"] >= 10
        assert report["category_summary"]["nl2sql_clarification"]["total"] >= 8
    finally:
        db.close()
        engine.dispose()


def test_memory_context_benchmark_detects_missing_project_context():
    broken_case = {
        "case_id": "MEM-BROKEN-001",
        "category": "project_reference",
        "flow": "session_memory",
        "session_id": "broken-001",
        "turns": [
            {
                "message": {"role": "user", "content": "查看 P001"},
                "context": {"project_id": "P001"},
            },
            {
                "message": {"role": "assistant", "content": "ok"},
                "context": {},
            },
            {
                "message": {"role": "user", "content": "继续"},
                "context": {"project_id": None},
            },
        ],
        "expected_resolved_context": {"project_id": "P999"},
        "expected_message_count": 3,
        "difficulty": "easy",
    }

    engine, db = _session()
    redis = FakeRedis()
    try:
        report = run_memory_context_benchmark(
            [broken_case],
            db=db,
            redis_client=redis,
            current_user=_user(),
        )
        assert report["total_cases"] == 1
        assert report["passed_cases"] == 0
        assert report["context_hit_rate"] == 0.0
        assert report["failures"][0]["case_id"] == "MEM-BROKEN-001"
    finally:
        db.close()
        engine.dispose()
