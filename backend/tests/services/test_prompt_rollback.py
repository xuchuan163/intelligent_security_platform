from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import AgentPromptVersion
from app.infrastructure.database.session import Base
from app.services.agents.prompt_registry import (
    activate_prompt_version,
    list_prompt_versions,
    prompt_version_to_dict,
    sync_agent_prompt_versions,
)


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def test_sync_creates_incremental_versions_when_hash_changes(monkeypatch):
    engine, db = _session()
    try:
        sync_agent_prompt_versions(db)
        first = get_version(db, "nl2sql_analyst", "v1.0")
        assert first is not None
        original_hash = first.prompt_hash

        monkeypatch.setattr(
            "app.services.agents.prompt_registry._prompt_hash",
            lambda _path: "changed-hash-001",
        )
        sync_agent_prompt_versions(db)

        archived = get_version(db, "nl2sql_analyst", "v1.0")
        active = db.query(AgentPromptVersion).filter_by(agent_code="nl2sql_analyst", is_active=True).one()
        assert archived is not None
        assert archived.is_active is False
        assert archived.status == "archived"
        assert archived.prompt_hash == original_hash
        assert active.prompt_version == "v1.1"
        assert active.prompt_hash == "changed-hash-001"
        assert active.is_active is True
    finally:
        db.close()
        engine.dispose()


def test_activate_prompt_version_switches_active_row():
    engine, db = _session()
    try:
        sync_agent_prompt_versions(db)
        old = AgentPromptVersion(
            agent_code="safety_supervisor",
            prompt_version="v0.9",
            prompt_path=str(Path("prompts/agents/safety_supervisor.md")),
            prompt_hash="legacy-hash",
            status="archived",
            is_active=False,
        )
        db.add(old)
        db.commit()

        activated = activate_prompt_version(db, agent_code="safety_supervisor", prompt_version="v0.9")
        rows = list_prompt_versions(db, agent_code="safety_supervisor")

        assert activated.prompt_version == "v0.9"
        assert activated.is_active is True
        assert sum(1 for row in rows if row.is_active) == 1
        assert next(row for row in rows if row.prompt_version == "v1.0").is_active is False
    finally:
        db.close()
        engine.dispose()


def test_activate_unknown_prompt_version_raises_value_error():
    engine, db = _session()
    try:
        sync_agent_prompt_versions(db)
        try:
            activate_prompt_version(db, agent_code="nl2sql_analyst", prompt_version="v9.9")
            assert False, "expected ValueError"
        except ValueError as exc:
            assert "not found" in str(exc)
    finally:
        db.close()
        engine.dispose()


def test_prompt_version_to_dict_exposes_activation_fields():
    engine, db = _session()
    try:
        sync_agent_prompt_versions(db)
        row = list_prompt_versions(db, agent_code="risk_profile_analyst")[0]
        payload = prompt_version_to_dict(row)
        assert payload["agent_code"] == "risk_profile_analyst"
        assert payload["prompt_version"] == "v1.0"
        assert payload["is_active"] is True
        assert payload["prompt_hash"]
        assert Path(payload["prompt_path"]).name.endswith(".md")
    finally:
        db.close()
        engine.dispose()


def get_version(db, agent_code: str, prompt_version: str) -> AgentPromptVersion | None:
    return (
        db.query(AgentPromptVersion)
        .filter_by(agent_code=agent_code, prompt_version=prompt_version)
        .one_or_none()
    )
