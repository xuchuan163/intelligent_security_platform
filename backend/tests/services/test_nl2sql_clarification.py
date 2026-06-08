from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.session import Base
from app.services.nl2sql.clarification import (
    append_clarification_reply,
    build_clarification_context,
    compose_refined_question,
    create_clarification_session,
    get_clarification_session,
    resolve_clarification_session,
)
from app.services.nl2sql.generator import MockCandidateSqlProvider, generate_candidate_sql
from app.services.nl2sql.prompt_builder import build_candidate_sql_prompt
from app.services.nl2sql.schema_context import build_schema_context


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
        user_id="U-CLR-01",
        user_name="Clarification User",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A",
        role="company_admin",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def test_compose_refined_question_includes_original_prompt_and_replies():
    refined = compose_refined_question(
        original_question="Show recent risky projects",
        clarification_prompt="please provide a time range",
        replies=["最近30天", "高风险指 risk_level=high"],
    )

    assert "Show recent risky projects" in refined
    assert "please provide a time range" in refined
    assert "最近30天" in refined
    assert "risk_level=high" in refined


def test_clarification_session_lifecycle_persists_in_checkpoint_table():
    engine, db = _session()
    try:
        user = _user()
        session = create_clarification_session(
            db,
            current_user=user,
            original_question="Show recent risky projects",
            clarification_prompt="please provide a time range",
            audit_id="NLSQL-TEST-001",
        )
        assert session["clarification_id"].startswith("NL2SQL-CLR-")
        assert session["status"] == "awaiting_clarification"

        updated = append_clarification_reply(
            db,
            current_user=user,
            clarification_id=session["clarification_id"],
            reply="最近30天，统计高风险项目",
        )
        assert updated["turn"] == 2
        assert len(updated["replies"]) == 1
        assert "最近30天" in updated["refined_question"]

        row = get_clarification_session(db, current_user=user, clarification_id=session["clarification_id"])
        assert row is not None
        assert row.status == "awaiting_clarification"

        resolved = resolve_clarification_session(
            db,
            current_user=user,
            clarification_id=session["clarification_id"],
            result_ref="NLSQL-RESOLVED-001",
        )
        assert resolved["status"] == "resolved"
    finally:
        db.close()
        engine.dispose()


def test_generator_uses_clarification_context_in_prompt_for_follow_up_turn():
    context = build_clarification_context(
        original_question="Show recent risky projects",
        clarification_prompt="please provide a time range",
        replies=["最近30天，高风险项目"],
    )
    provider = MockCandidateSqlProvider(
        "select project_id, risk_level from project_risk_profile where risk_level = 'high'"
    )

    result = generate_candidate_sql(
        context["refined_question"],
        _user(),
        provider,
        clarification_context=context,
    )

    assert result.status == "audit_passed"
    assert provider.last_prompt is not None
    assert "Clarification context:" in provider.last_prompt
    assert "最近30天" in provider.last_prompt


def test_prompt_builder_renders_clarification_block():
    prompt = build_candidate_sql_prompt(
        question="ignored",
        schema_context=build_schema_context(),
        clarification_context=build_clarification_context(
            original_question="Show top projects",
            clarification_prompt="specify ranking metric",
            replies=["按风险分排名"],
        ),
    )

    assert "Refined question:" in prompt
    assert "按风险分排名" in prompt
