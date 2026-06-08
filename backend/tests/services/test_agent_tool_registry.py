import pytest

from app.core.security import MockUser, ScopeType


def _project_user() -> MockUser:
    return MockUser(
        user_id="U-PROJECT",
        user_name="Project User",
        tenant_id="COMPANY-A",
        company_id="COMPANY-A",
        org_path="COMPANY-A/P002",
        role="project_safety_officer",
        scope_type=ScopeType.PROJECT,
        authorized_project_ids=("P002",),
    )


def test_registry_exposes_read_only_tools_as_controlled_executable():
    from app.services.agents.tool_registry import ToolExecutionContext, evaluate_tool_access, get_tool_definition

    tool = get_tool_definition("work_orders.read")
    decision = evaluate_tool_access(
        tool.name,
        ToolExecutionContext(
            execution_mode="controlled_execute",
            current_user=_project_user(),
            project_id="P002",
        ),
    )

    assert tool.side_effect == "read_only"
    assert decision.status == "ready"
    assert decision.will_execute is True
    assert decision.reason is None


def test_dry_run_validates_read_only_tool_without_execution():
    from app.services.agents.tool_registry import ToolExecutionContext, evaluate_tool_access

    decision = evaluate_tool_access(
        "rules.read_triggers",
        ToolExecutionContext(
            execution_mode="dry_run",
            current_user=_project_user(),
            project_id="P002",
        ),
    )

    assert decision.status == "dry_run_passed"
    assert decision.will_execute is False
    assert decision.reason is None


def test_write_side_tools_require_approval_and_never_execute():
    from app.services.agents.tool_registry import ToolExecutionContext, evaluate_tool_access

    decision = evaluate_tool_access(
        "work_orders.transition",
        ToolExecutionContext(
            execution_mode="controlled_execute",
            current_user=_project_user(),
            project_id="P002",
        ),
    )

    assert decision.status == "approval_required"
    assert decision.will_execute is False
    assert "write-side" in decision.reason


def test_restricted_tools_are_blocked():
    from app.services.agents.tool_registry import ToolExecutionContext, evaluate_tool_access

    decision = evaluate_tool_access(
        "stop_work.issue",
        ToolExecutionContext(
            execution_mode="controlled_execute",
            current_user=_project_user(),
            project_id="P002",
        ),
    )

    assert decision.status == "blocked"
    assert decision.will_execute is False
    assert "restricted" in decision.reason


def test_project_user_cannot_access_unauthorized_project():
    from app.services.agents.tool_registry import ToolExecutionContext, evaluate_tool_access

    decision = evaluate_tool_access(
        "hazards.read",
        ToolExecutionContext(
            execution_mode="controlled_execute",
            current_user=_project_user(),
            project_id="P999",
        ),
    )

    assert decision.status == "blocked"
    assert decision.will_execute is False
    assert "project" in decision.reason


def test_unknown_tool_is_rejected():
    from app.services.agents.tool_registry import UnknownAgentToolError, get_tool_definition

    with pytest.raises(UnknownAgentToolError):
        get_tool_definition("unknown.tool")
