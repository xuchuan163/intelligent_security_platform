from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import DataScope, MockUser
from app.infrastructure.database.session import Base
from app.services.memory.agent_bridge import (
    enrich_nl2sql_question,
    prepare_request_context,
    record_agent_interaction,
    record_nl2sql_interaction,
)
from app.services.memory.service import append_session_memory, get_session_memory


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
        user_id="U-MEM-BRIDGE",
        user_name="Bridge User",
        tenant_id="TENANT-A",
        org_path="TENANT-A",
        role="platform_admin",
        data_scope=DataScope.TENANT,
    )


def test_prepare_request_context_merges_prior_session_entities():
    engine, db = _session()
    redis = FakeRedis()
    try:
        append_session_memory(
            db,
            redis,
            current_user=_user(),
            session_id="S-BRIDGE-001",
            message={"role": "assistant", "content": "P001 is high risk"},
            context={"project_id": "P001", "risk_level": "high"},
        )
        merged, memory = prepare_request_context(
            db,
            redis,
            current_user=_user(),
            session_id="S-BRIDGE-001",
            incoming_context={"intent": "follow_up"},
        )
        assert memory is not None
        assert merged["project_id"] == "P001"
        assert merged["intent"] == "follow_up"
    finally:
        db.close()
        engine.dispose()


def test_record_agent_interaction_persists_user_and_assistant_turns():
    engine, db = _session()
    redis = FakeRedis()
    try:
        record_agent_interaction(
            db,
            redis,
            current_user=_user(),
            session_id="S-BRIDGE-002",
            user_message="它的风险驱动因素是什么？",
            result={
                "target_agent": "risk_profile_analyst",
                "intent": "risk_profile",
                "route_reason": "profile follow-up",
            },
            merged_context={"project_id": "P001"},
        )
        memory = get_session_memory(db, redis, current_user=_user(), session_id="S-BRIDGE-002")
        assert memory is not None
        assert memory["message_count"] == 2
        assert memory["context"]["project_id"] == "P001"
        assert memory["context"]["last_target_agent"] == "risk_profile_analyst"
    finally:
        db.close()
        engine.dispose()


def test_enrich_nl2sql_question_adds_project_context_for_pronoun_follow_up():
    memory = {
        "context": {"project_id": "P001", "last_question": "列出高风险项目"},
        "messages": [],
    }
    enriched = enrich_nl2sql_question("继续按上次的项目范围统计", memory)
    assert "P001" in enriched


def test_record_nl2sql_interaction_persists_audit_metadata():
    engine, db = _session()
    redis = FakeRedis()
    try:
        record_nl2sql_interaction(
            db,
            redis,
            current_user=_user(),
            session_id="S-BRIDGE-003",
            question="列出高风险项目",
            result={
                "audit_id": "NLSQL-TEST-001",
                "status": "audit_passed",
                "sanitized_sql": "select project_id from project_risk_profile",
            },
            merged_context={"project_id": "P001"},
        )
        memory = get_session_memory(db, redis, current_user=_user(), session_id="S-BRIDGE-003")
        assert memory is not None
        assert memory["context"]["last_audit_id"] == "NLSQL-TEST-001"
        assert memory["context"]["last_nl2sql_status"] == "audit_passed"
    finally:
        db.close()
        engine.dispose()
