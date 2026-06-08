from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.core.security import MockUser, ScopeType


ToolSideEffect = Literal["read_only", "write", "restricted"]
ToolAccessStatus = Literal["ready", "dry_run_passed", "approval_required", "blocked"]


class UnknownAgentToolError(KeyError):
    pass


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    side_effect: ToolSideEffect
    description: str


@dataclass(frozen=True)
class ToolExecutionContext:
    execution_mode: Literal["dry_run", "controlled_execute"]
    current_user: MockUser
    project_id: str | None = None


@dataclass(frozen=True)
class ToolAccessDecision:
    status: ToolAccessStatus
    will_execute: bool
    reason: str | None = None


_TOOLS: dict[str, ToolDefinition] = {
    "profile.read": ToolDefinition("profile.read", "read_only", "Read risk profile summaries."),
    "rules.read_triggers": ToolDefinition("rules.read_triggers", "read_only", "Read rule trigger evidence."),
    "work_orders.read": ToolDefinition("work_orders.read", "read_only", "Read work-order state and detail."),
    "hazards.read": ToolDefinition("hazards.read", "read_only", "Read hazard ledger and detail."),
    "metrics.read_catalog": ToolDefinition("metrics.read_catalog", "read_only", "Read metric catalog metadata."),
    "nl2sql.audit_only": ToolDefinition("nl2sql.audit_only", "read_only", "Generate and audit candidate SQL."),
    "nl2sql.readonly_execute": ToolDefinition("nl2sql.readonly_execute", "read_only", "Execute audited read-only SQL."),
    "cases.read": ToolDefinition("cases.read", "read_only", "Read accident case summaries."),
    "knowledge.search": ToolDefinition("knowledge.search", "read_only", "Search safety knowledge and accident cases."),
    "graph.read_neighbors": ToolDefinition("graph.read_neighbors", "read_only", "Read one-hop graph neighbors for a node."),
    "memory.read_context": ToolDefinition("memory.read_context", "read_only", "Read session memory summary."),
    "work_orders.create": ToolDefinition("work_orders.create", "write", "Create a work order."),
    "work_orders.dispatch": ToolDefinition("work_orders.dispatch", "write", "Dispatch a work order."),
    "work_orders.transition": ToolDefinition("work_orders.transition", "write", "Transition a work order."),
    "hazards.create": ToolDefinition("hazards.create", "write", "Create a hazard."),
    "penalty.create": ToolDefinition("penalty.create", "restricted", "Create a penalty."),
    "stop_work.issue": ToolDefinition("stop_work.issue", "restricted", "Issue a stop-work action."),
    "subcontractor.remove": ToolDefinition("subcontractor.remove", "restricted", "Remove a subcontractor."),
}


def list_tool_definitions() -> list[ToolDefinition]:
    return list(_TOOLS.values())


def get_tool_definition(tool_name: str) -> ToolDefinition:
    try:
        return _TOOLS[tool_name]
    except KeyError as exc:
        raise UnknownAgentToolError(tool_name) from exc


def evaluate_tool_access(tool_name: str, context: ToolExecutionContext) -> ToolAccessDecision:
    tool = get_tool_definition(tool_name)
    project_reason = _project_access_reason(context.current_user, context.project_id)
    if project_reason:
        return ToolAccessDecision(status="blocked", will_execute=False, reason=project_reason)

    if tool.side_effect == "restricted":
        return ToolAccessDecision(
            status="blocked",
            will_execute=False,
            reason=f"restricted tool {tool.name} cannot be executed by controlled DAG v1",
        )
    if tool.side_effect == "write":
        return ToolAccessDecision(
            status="approval_required",
            will_execute=False,
            reason=f"write-side tool {tool.name} requires human approval",
        )
    if context.execution_mode == "dry_run":
        return ToolAccessDecision(status="dry_run_passed", will_execute=False)
    return ToolAccessDecision(status="ready", will_execute=True)


def _project_access_reason(current_user: MockUser, project_id: str | None) -> str | None:
    if (
        project_id
        and current_user.scope_type == ScopeType.PROJECT
        and current_user.authorized_project_ids
        and project_id not in current_user.authorized_project_ids
    ):
        return f"project {project_id} is outside authorized project scope"
    return None
