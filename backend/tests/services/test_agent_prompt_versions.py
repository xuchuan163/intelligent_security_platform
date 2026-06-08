from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import AgentPromptVersion
from app.infrastructure.database.session import Base
from app.services.agents.prompt_registry import (
    AGENT_PROMPT_SPECS,
    get_active_prompt_version,
    list_active_prompt_versions,
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


def test_agent_prompt_version_model_is_registered_in_metadata():
    assert AgentPromptVersion.__tablename__ in Base.metadata.tables
    columns = Base.metadata.tables[AgentPromptVersion.__tablename__].columns
    assert "agent_code" in columns
    assert "prompt_hash" in columns
    assert "is_active" in columns


def test_sync_agent_prompt_versions_registers_six_active_prompts():
    engine, db = _session()
    try:
        result = sync_agent_prompt_versions(db)
        active = list_active_prompt_versions(db)

        assert result["synced_count"] == 6
        assert len(active) == 6
        assert {row.agent_code for row in active} == {spec.agent_code for spec in AGENT_PROMPT_SPECS}
        assert all(row.prompt_version == "v1.0" for row in active)
        assert all(row.is_active for row in active)
        assert all(row.prompt_hash for row in active)
        for row in active:
            assert Path(row.prompt_path).exists()
    finally:
        db.close()
        engine.dispose()


def test_get_active_prompt_version_returns_single_agent_prompt():
    engine, db = _session()
    try:
        sync_agent_prompt_versions(db)
        row = get_active_prompt_version(db, "nl2sql_analyst")

        assert row is not None
        assert row.agent_code == "nl2sql_analyst"
        assert row.prompt_path.endswith("nl2sql_analyst.md")
    finally:
        db.close()
        engine.dispose()
