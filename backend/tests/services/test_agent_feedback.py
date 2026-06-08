import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.security import DataScope, MockUser, ScopeType
from app.infrastructure.database.models import AgentFeedback
from app.infrastructure.database.session import Base
from app.services.agents.feedback import create_agent_feedback, list_agent_feedback


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    return engine, SessionLocal()


def _company_user() -> MockUser:
    return MockUser(
        user_id="U-FB-01",
        user_name="Feedback User",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A",
        role="company_admin",
        data_scope=DataScope.TENANT,
        scope_type=ScopeType.COMPANY,
    )


def test_create_thumb_feedback_persists_pending_label():
    engine, db = _session()
    try:
        result = create_agent_feedback(
            db,
            current_user=_company_user(),
            task_id="AGDAG-FEEDBACK-001",
            agent_name="hazard_rectification_advisor",
            feedback_type="thumb",
            rating=1,
            feedback_reason="helpful suggestion",
            original_output={"status": "generated"},
            project_id="P001",
        )
        assert result["feedback_id"].startswith("AGFB-")
        assert result["label_status"] == "pending"
        assert result["used_for_prompt_tuning"] is False
        assert result["rating"] == 1

        row = db.query(AgentFeedback).filter_by(feedback_id=result["feedback_id"]).one()
        assert row.agent_name == "hazard_rectification_advisor"
    finally:
        db.close()
        engine.dispose()


def test_create_correction_feedback_requires_text_or_output():
    engine, db = _session()
    try:
        with pytest.raises(ValueError, match="correction_text or corrected_output"):
            create_agent_feedback(
                db,
                current_user=_company_user(),
                task_id="AGDAG-FEEDBACK-002",
                agent_name="nl2sql_analyst",
                feedback_type="correction",
            )
    finally:
        db.close()
        engine.dispose()


def test_list_feedback_is_scoped_to_company():
    engine, db = _session()
    try:
        create_agent_feedback(
            db,
            current_user=_company_user(),
            task_id="AGDAG-FEEDBACK-003",
            agent_name="work_order_coordinator",
            feedback_type="adoption",
            related_work_order_id="WO-DEMO-001",
        )
        create_agent_feedback(
            db,
            current_user=MockUser(
                user_id="U-OTHER",
                user_name="Other",
                tenant_id="COMPANY-B",
                company_id="COMPANY-B",
                org_path="COMPANY-B",
                role="company_admin",
                scope_type=ScopeType.COMPANY,
            ),
            task_id="AGDAG-FEEDBACK-004",
            agent_name="work_order_coordinator",
            feedback_type="thumb",
            rating=-1,
        )

        result = list_agent_feedback(db, current_user=_company_user(), agent_name="work_order_coordinator")
        assert result["total"] == 1
        assert result["items"][0]["task_id"] == "AGDAG-FEEDBACK-003"
    finally:
        db.close()
        engine.dispose()
