from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import AgentPromptVersion
from app.infrastructure.database.session import Base, get_db
from app.main import app
from app.services.agents.prompt_registry import sync_agent_prompt_versions


def _headers() -> dict[str, str]:
    return {
        "X-Tenant-Id": "COMPANY-A",
        "X-Company-Id": "COMPANY-A",
        "X-Mock-User-Id": "U-PROMPT-API",
    }


def test_get_prompts_lists_versions_and_activate_rolls_back(monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)

    original_hash = db.query(AgentPromptVersion).filter_by(agent_code="nl2sql_analyst", prompt_version="v1.0").one().prompt_hash
    monkeypatch.setattr(
        "app.services.agents.prompt_registry._prompt_hash",
        lambda _path: "changed-hash-api",
    )
    sync_agent_prompt_versions(db)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        list_response = client.get("/api/v1/agent/prompts", params={"agent_code": "nl2sql_analyst"}, headers=_headers())
        assert list_response.status_code == 200
        items = list_response.json()["data"]["items"]
        assert len(items) >= 2
        assert any(item["prompt_version"] == "v1.1" and item["is_active"] for item in items)

        activate_response = client.post(
            "/api/v1/agent/prompts/nl2sql_analyst/activate",
            json={"prompt_version": "v1.0"},
            headers=_headers(),
        )
        assert activate_response.status_code == 200
        activated = activate_response.json()["data"]
        assert activated["prompt_version"] == "v1.0"
        assert activated["is_active"] is True
        assert activated["prompt_hash"] == original_hash
        assert Path(activated["prompt_path"]).name == "nl2sql_analyst.md"
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
