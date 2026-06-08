from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.session import Base, get_db
from app.main import app
from app.services.agents.prompt_registry import sync_agent_prompt_versions


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    def get(self, key: str) -> str | None:
        return self.values.get(key)


def _headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": "COMPANY-A",
        "X-Company-Id": "COMPANY-A",
        "X-Mock-User-Id": "U-MEM-API",
    }


def test_agent_ask_reuses_session_context_for_follow_up_turn():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)
    redis = FakeRedis()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    from app.api.v1.endpoints import agent as agent_endpoint

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[agent_endpoint.get_redis_client_optional] = lambda: redis
    try:
        client = TestClient(app)
        session_id = "API-SESSION-001"
        first = client.post(
            "/api/v1/agent/ask",
            json={
                "message": "解释 P001 项目画像风险为什么是 high",
                "session_id": session_id,
                "context": {"project_id": "P001"},
                "execution_mode": "route_only",
            },
            headers=_headers(),
        )
        assert first.status_code == 200
        assert first.json()["data"]["session_id"] == session_id

        second = client.post(
            "/api/v1/agent/ask",
            json={
                "message": "它的风险驱动因素是什么？",
                "session_id": session_id,
                "context": {},
                "execution_mode": "route_only",
            },
            headers=_headers(),
        )
        assert second.status_code == 200
        data = second.json()["data"]
        assert data["context"]["project_id"] == "P001"
        assert data["memory_source"] == "redis"
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(agent_endpoint.get_redis_client_optional, None)
        db.close()
        engine.dispose()
