from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.session import Base
from app.services.agents.prompt_registry import sync_agent_prompt_versions
from app.services.agents.router import route_agent_message


class FakeQwenClient:
    def __init__(self, available: bool = True, content: str | None = None, message: str = "ok") -> None:
        self.available = available
        self.content = content
        self.message = message
        self.messages = None

    def chat(self, messages, temperature=0.0):
        self.messages = messages
        return {
            "available": self.available,
            "message": self.message,
            "content": self.content,
        }


def _session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()
    sync_agent_prompt_versions(db)
    return engine, db


def test_routes_representative_messages_to_six_agents():
    engine, db = _session()
    try:
        cases = [
            ("帮我判断这条安全问题应该交给谁处理", "safety_supervisor", "general_safety"),
            ("解释 P001 项目画像风险为什么是 high", "risk_profile_analyst", "risk_profile"),
            ("SR-PROJ-001 为什么触发，证据是什么", "rule_compliance_checker", "rule_compliance"),
            ("查看 WO001 工单是否超期并说明闭环动作", "work_order_coordinator", "work_order"),
            ("查询项目风险排名前十", "nl2sql_analyst", "nl2sql"),
            ("这个临边防护隐患应该怎么整改", "hazard_rectification_advisor", "hazard_rectification"),
        ]
        for message, agent_code, intent in cases:
            result = route_agent_message(db, message, context={})
            assert result["target_agent"] == agent_code
            assert result["intent"] == intent
            assert result["prompt_version"] == "v1.0"
            assert result["execution_mode"] == "route_only"
    finally:
        db.close()
        engine.dispose()


def test_punitive_or_stop_work_language_requires_human_review():
    engine, db = _session()
    try:
        result = route_agent_message(db, "建议立即停工并清退这个分包商", context={"project_id": "P001"})

        assert result["need_human_review"] is True
        assert "restricted_action" in result["blocked_actions"]
        assert result["execution_mode"] == "route_only"
    finally:
        db.close()
        engine.dispose()


def test_execute_preview_calls_llm_and_attaches_structured_preview():
    engine, db = _session()
    try:
        client = FakeQwenClient(
            content=(
                '{"route_explanation":"query intent",'
                '"expected_inputs":["question"],'
                '"evidence_needed":["metric_code"],'
                '"safety_notes":["audit first"],'
                '"need_human_review":false}'
            )
        )

        result = route_agent_message(
            db,
            "查询项目风险排名",
            context={"project_id": "P001"},
            execution_mode="execute_preview",
            llm_client=client,
        )

        assert result["target_agent"] == "nl2sql_analyst"
        assert result["execution_mode"] == "execute_preview"
        assert result["preview_status"] == "generated"
        assert result["llm_available"] is True
        assert result["llm_preview"]["route_explanation"] == "query intent"
        assert "nl2sql_analyst v1.0" in client.messages[0]["content"]
    finally:
        db.close()
        engine.dispose()


def test_execute_preview_handles_unavailable_llm_without_failing_route():
    engine, db = _session()
    try:
        result = route_agent_message(
            db,
            "查询项目风险排名",
            context={},
            execution_mode="execute_preview",
            llm_client=FakeQwenClient(available=False, content=None, message="not configured"),
        )

        assert result["target_agent"] == "nl2sql_analyst"
        assert result["preview_status"] == "llm_unavailable"
        assert result["llm_available"] is False
        assert result["llm_preview"] is None
    finally:
        db.close()
        engine.dispose()


def test_execute_preview_cannot_downgrade_restricted_action_human_review():
    engine, db = _session()
    try:
        result = route_agent_message(
            db,
            "建议立即停工并处罚责任分包",
            context={"project_id": "P001"},
            execution_mode="execute_preview",
            llm_client=FakeQwenClient(content='{"route_explanation":"ok","need_human_review":false}'),
        )

        assert result["need_human_review"] is True
        assert result["blocked_actions"] == ["restricted_action"]
        assert result["preview_status"] == "generated"
    finally:
        db.close()
        engine.dispose()


def test_plan_only_returns_auditable_dag_steps_without_execution():
    engine, db = _session()
    try:
        result = route_agent_message(
            db,
            "explain the project risk score drivers",
            context={"project_id": "P001"},
            execution_mode="plan_only",
        )

        assert result["execution_mode"] == "plan_only"
        assert result["dag_status"] == "planned"
        assert result["dag_execution_allowed"] is False
        assert result["planned_steps"]
        assert result["planned_steps"][0]["agent_code"] == "safety_supervisor"
        assert result["planned_steps"][0]["action"] == "classify_intent_and_route"
        assert all(step["will_execute"] is False for step in result["planned_steps"])
        assert all("step_id" in step for step in result["planned_steps"])
        assert all("depends_on" in step for step in result["planned_steps"])
    finally:
        db.close()
        engine.dispose()


def test_plan_only_nl2sql_references_guarded_api_without_sql_execution():
    engine, db = _session()
    try:
        result = route_agent_message(
            db,
            "sql list top 10 high risk projects",
            context={"project_id": "P001"},
            execution_mode="plan_only",
        )

        assert result["target_agent"] == "nl2sql_analyst"
        assert result["intent"] == "nl2sql"
        nl2sql_steps = [
            step for step in result["planned_steps"] if step["agent_code"] == "nl2sql_analyst"
        ]
        assert nl2sql_steps
        gate_steps = [step for step in nl2sql_steps if step["action"] == "prepare_guarded_nl2sql_request"]
        assert gate_steps
        assert gate_steps[0]["tool_name"] == "POST /api/v1/agent/nl2sql"
        assert gate_steps[0]["will_execute"] is False
        assert "execute_sql" not in {step["action"] for step in result["planned_steps"]}
    finally:
        db.close()
        engine.dispose()


def test_plan_only_restricted_action_marks_review_on_route_and_steps():
    engine, db = _session()
    try:
        result = route_agent_message(
            db,
            "stop work and remove subcontractor because the hazard is critical",
            context={"project_id": "P001"},
            execution_mode="plan_only",
        )

        assert result["need_human_review"] is True
        assert result["blocked_actions"] == ["restricted_action"]
        review_steps = [
            step for step in result["planned_steps"] if step["requires_human_review"] is True
        ]
        assert review_steps
        assert all(step["will_execute"] is False for step in review_steps)
    finally:
        db.close()
        engine.dispose()


def test_plan_only_assigns_read_only_tools_for_profile_rule_hazard_and_metric_branches():
    engine, db = _session()
    try:
        cases = [
            ("explain project profile risk score", "profile.read"),
            ("explain SR-PROJ-001 rule trigger evidence", "rules.read_triggers"),
            ("explain this hazard rectification evidence", "hazards.read"),
            ("list metric catalog aliases", "metrics.read_catalog"),
        ]
        for message, expected_tool in cases:
            result = route_agent_message(
                db,
                message,
                context={"project_id": "P001"},
                execution_mode="plan_only",
            )
            tools = {step.get("tool_name") for step in result["planned_steps"]}
            assert expected_tool in tools
    finally:
        db.close()
        engine.dispose()
