from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.v1.endpoints import memory
from app.infrastructure.database.session import Base


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    def get(self, key: str) -> str | None:
        return self.values.get(key)


def test_memory_session_route_round_trips_with_success_envelope():
    client = TestClient(app)
    fake_redis = FakeRedis()
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[memory.get_redis_client] = lambda: fake_redis
    app.dependency_overrides[memory.get_db] = override_db

    try:
        response = client.post(
            "/api/v1/memory/session",
            json={
                "session_id": "S-API-001",
                "message": {"role": "user", "content": "这个项目有什么风险?"},
                "context": {"project_id": "P001", "full_sql_result": [{"id": 1}]},
                "summary": "用户询问项目风险",
            },
            headers={
                "X-Mock-User-Id": "u-api-001",
                "X-Tenant-Id": "TENANT-A",
                "X-Org-Path": "TENANT-A/BU-01",
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["code"] == "SUCCESS"
        assert body["data"]["session_id"] == "S-API-001"
        assert body["data"]["store_full_sql_result"] is False

        read_response = client.get(
            "/api/v1/memory/session",
            params={"session_id": "S-API-001"},
            headers={
                "X-Mock-User-Id": "u-api-001",
                "X-Tenant-Id": "TENANT-A",
                "X-Org-Path": "TENANT-A/BU-01",
            },
        )
        assert read_response.status_code == 200
        assert read_response.json()["data"]["context"] == {"project_id": "P001"}
    finally:
        app.dependency_overrides.clear()


def test_memory_session_requires_session_id():
    client = TestClient(app)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[memory.get_redis_client] = lambda: FakeRedis()
    app.dependency_overrides[memory.get_db] = override_db

    try:
        response = client.post("/api/v1/memory/session", json={"message": {"role": "user", "content": "hi"}})

        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
