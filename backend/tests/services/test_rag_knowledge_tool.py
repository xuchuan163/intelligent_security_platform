import datetime as dt

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import AccidentCaseLibrary
from app.services.agents.dag_executor import _execute_read_only_tool
from app.services.agents.tool_registry import ToolExecutionContext, evaluate_tool_access


def _session_factory():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.infrastructure.database.session import Base

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _user() -> MockUser:
    return MockUser(
        user_id="U-RAG",
        user_name="RAG User",
        tenant_id="CSCEC",
        org_path="CSCEC",
        role="company_analyst",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def test_knowledge_search_tool_is_read_only_and_executable():
    decision = evaluate_tool_access(
        "knowledge.search",
        ToolExecutionContext(
            execution_mode="controlled_execute",
            current_user=_user(),
            project_id="P001",
        ),
    )

    assert decision.status == "ready"
    assert decision.will_execute is True


def test_execute_knowledge_search_returns_evidence_refs(monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "milvus_enabled", False)
    db = _session_factory()
    db.add(
        AccidentCaseLibrary(
            accident_case_id="AC-TOOL-001",
            tenant_id="CSCEC",
            accident_type="坍塌",
            severity="一般事故",
            direct_cause="基坑边坡开裂",
            indirect_cause="监测不足",
            rectification_measures="补强支护",
            tags=["基坑"],
            status="active",
            created_at=dt.datetime(2026, 6, 1, 9, 0, 0),
        )
    )
    db.commit()

    result = _execute_read_only_tool(
        db,
        tool_name="knowledge.search",
        current_user=_user(),
        project_id="P001",
        context={"query": "基坑"},
    )

    assert result["row_count"] >= 1
    assert result["evidence"]
    assert result["evidence"][0]["type"] == "rag_hit"
