import datetime as dt
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.cache import (
    EMPTY_CACHE_MARKER,
    hash_question,
    invalidate_profile_cache,
    nl2sql_cache_key,
    profile_cache_key,
    read_nl2sql_cache,
    read_profile_cache,
    write_nl2sql_cache,
)
from app.infrastructure.database.models import Project, ProjectRiskProfile
from app.infrastructure.database.session import Base
from app.services.profiles.service import get_project_profile, recalculate_project_profiles


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def delete(self, key: str) -> int:
        existed = key in self.values
        self.values.pop(key, None)
        self.ttls.pop(key, None)
        return 1 if existed else 0

    def ping(self) -> bool:
        return True


def _session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def _seed_project(db) -> None:
    db.add(
        Project(
            project_id="P001",
            tenant_id="CSCEC",
            org_path="CSCEC/P001",
            project_name="演示项目",
            status="active",
        )
    )
    db.add(
        ProjectRiskProfile(
            project_id="P001",
            tenant_id="CSCEC",
            org_path="CSCEC/P001",
            calc_date=dt.date(2026, 6, 3),
            total_risk_score=42.0,
            risk_level="medium",
            data_completeness=0.8,
            confidence_level="medium",
            risk_tags={"tags": ["demo"]},
            explanation="demo",
            suggestion="demo",
        )
    )
    db.commit()


def _user() -> MockUser:
    return MockUser(
        user_id="U-CACHE",
        user_name="Cache User",
        tenant_id="CSCEC",
        org_path="CSCEC",
        role="company_analyst",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def test_profile_cache_hit_and_invalidate(monkeypatch):
    monkeypatch.setattr(settings, "cache_profile_ttl_seconds", 600)
    monkeypatch.setattr(settings, "cache_empty_ttl_seconds", 60)
    db = _session()
    _seed_project(db)
    redis = FakeRedis()
    key = profile_cache_key("project", "P001")

    first = get_project_profile(db, "P001", current_user=_user(), redis_client=redis)
    assert first is not None
    assert key in redis.values

    second = get_project_profile(db, "P001", current_user=_user(), redis_client=redis)
    assert second == first

    invalidate_profile_cache(redis, "project", "P001")
    assert key not in redis.values


def test_profile_empty_result_uses_short_ttl():
    redis = FakeRedis()
    calls = {"count": 0}

    def loader():
        calls["count"] += 1
        return None

    assert read_profile_cache(redis, "project", "P404", loader) is None
    assert calls["count"] == 1
    key = profile_cache_key("project", "P404")
    assert redis.ttls[key] == settings.cache_empty_ttl_seconds
    assert json.loads(redis.values[key]) == EMPTY_CACHE_MARKER

    assert read_profile_cache(redis, "project", "P404", loader) is None
    assert calls["count"] == 1


def test_nl2sql_cache_key_uses_tenant_and_question_hash():
    redis = FakeRedis()
    tenant_id = "CSCEC"
    question = "统计高风险项目数量"
    payload = {
        "status": "audit_passed",
        "question": question,
        "sanitized_sql": "SELECT project_id FROM project_risk_profile",
        "tables_used": ["project_risk_profile"],
        "fields_used": ["project_id"],
        "scope_injected": True,
    }
    write_nl2sql_cache(redis, tenant_id, question, payload)

    key = nl2sql_cache_key(tenant_id, hash_question(question))
    assert key in redis.values
    assert redis.ttls[key] == settings.cache_nl2sql_ttl_seconds
    assert read_nl2sql_cache(redis, tenant_id, question) == payload


def test_recalculate_project_profiles_invalidates_cache(monkeypatch):
    db = _session()
    _seed_project(db)
    redis = FakeRedis()
    key = profile_cache_key("project", "P001")
    monkeypatch.setattr("app.services.profiles.service.build_redis_client_optional", lambda: redis)

    get_project_profile(db, "P001", current_user=_user(), redis_client=redis)
    assert key in redis.values

    recalculate_project_profiles(db, current_user=_user())
    assert key not in redis.values


def test_invalidate_profile_cache_deletes_key():
    redis = FakeRedis()
    key = profile_cache_key("worker", "W001")
    redis.setex(key, 600, json.dumps({"worker_id": "W001"}))
    invalidate_profile_cache(redis, "worker", "W001")
    assert redis.get(key) is None
