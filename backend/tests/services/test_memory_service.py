import datetime as dt
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.security import DataScope, MockUser
from app.infrastructure.database.models import AgentSessionSummary, AgentTaskCheckpoint
from app.infrastructure.database.session import Base
from app.services.memory.service import (
    MEMORY_TTL_SECONDS,
    append_session_memory,
    get_session_memory,
    save_task_checkpoint,
)


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
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _user() -> MockUser:
    return MockUser(
        user_id="u-agent-001",
        user_name="Agent User",
        tenant_id="TENANT-A",
        org_path="TENANT-A/BU-01",
        role="safety_manager",
        data_scope=DataScope.ORG,
    )


def test_append_session_memory_uses_expected_key_ttl_and_sanitizes_sql_result():
    db = _session()
    redis = FakeRedis()

    result = append_session_memory(
        db,
        redis,
        current_user=_user(),
        session_id="S-001",
        message={"role": "assistant", "content": "已完成风险分析"},
        context={
            "project_id": "P001",
            "full_sql_result": [{"worker_name": "张三"}],
            "nested": {"raw_video": "video-bytes", "keep": "safe"},
        },
        summary="项目风险分析摘要",
    )

    key = "session:u-agent-001:S-001"
    assert redis.ttls[key] == MEMORY_TTL_SECONDS == 1800
    stored = json.loads(redis.values[key])
    assert stored["store_full_sql_result"] is False
    assert stored["context"] == {"project_id": "P001", "nested": {"keep": "safe"}}
    assert stored["messages"] == [{"role": "assistant", "content": "已完成风险分析"}]
    assert result["source"] == "redis"

    row = db.query(AgentSessionSummary).filter_by(session_id="S-001").one()
    assert row.tenant_id == "TENANT-A"
    assert row.org_path == "TENANT-A/BU-01"
    assert row.user_id == "u-agent-001"
    assert row.summary == "项目风险分析摘要"
    assert row.message_count == 1


def test_get_session_memory_falls_back_to_mysql_summary_without_full_messages():
    db = _session()
    redis = FakeRedis()
    db.add(
        AgentSessionSummary(
            tenant_id="TENANT-A",
            org_path="TENANT-A/BU-01",
            user_id="u-agent-001",
            session_id="S-002",
            summary="历史会话摘要",
            message_count=6,
            last_message_at=dt.datetime(2026, 6, 4, 9, 30, 0),
        )
    )
    db.commit()

    result = get_session_memory(db, redis, current_user=_user(), session_id="S-002")

    assert result == {
        "session_id": "S-002",
        "user_id": "u-agent-001",
        "tenant_id": "TENANT-A",
        "messages": [],
        "context": {},
        "summary": "历史会话摘要",
        "message_count": 6,
        "store_full_sql_result": False,
        "source": "mysql_summary",
    }


def test_save_task_checkpoint_writes_mysql_and_redis_hot_state_with_scope():
    db = _session()
    redis = FakeRedis()

    result = save_task_checkpoint(
        db,
        redis,
        current_user=_user(),
        task_id="TASK-001",
        task_type="memory_session",
        status="running",
        context={"step": "collect_context", "sql_result": [{"secret": "drop"}]},
        sub_tasks=[{"name": "load_profile", "status": "done"}],
    )

    key = "checkpoint:u-agent-001:TASK-001"
    assert redis.ttls[key] == MEMORY_TTL_SECONDS
    assert json.loads(redis.values[key])["context"] == {"step": "collect_context"}
    assert result["task_id"] == "TASK-001"

    row = db.query(AgentTaskCheckpoint).filter_by(task_id="TASK-001").one()
    assert row.tenant_id == "TENANT-A"
    assert row.org_path == "TENANT-A/BU-01"
    assert row.context_json == {"step": "collect_context"}
