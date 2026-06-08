from __future__ import annotations

import datetime as dt
import time
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.core.security import MockUser, assert_project_access
from app.infrastructure.database.models import (
    AgentDagRun,
    AgentDagStepRun,
    Hazard,
    MetricCatalog,
    ProjectRiskProfile,
    RuleTriggerLog,
    SafetyWorkOrder,
)
from app.infrastructure.llm.qwen_client import qwen
from app.services.agents.approval_queue import create_approval_request_for_step
from app.services.agents.hazard_rectification import draft_rectification_suggestion
from app.services.agents.tool_registry import ToolExecutionContext, UnknownAgentToolError, evaluate_tool_access
from app.infrastructure.neo4j_client import build_neo4j_client_optional
from app.services.graph.neighbors import get_graph_neighbors
from app.services.rag.service import search_rag


AgentDagExecutionMode = Literal["dry_run", "controlled_execute"]


def execute_agent_dag(
    db: Session,
    *,
    route_result: dict[str, Any],
    message: str,
    context: dict[str, Any] | None,
    current_user: MockUser,
    execution_mode: AgentDagExecutionMode,
) -> dict[str, Any]:
    context = context or {}
    project_id = context.get("project_id")
    planned_steps = route_result.get("planned_steps") or []
    run_id = f"AGDAG-{uuid.uuid4().hex[:16]}"
    started_at = _now()

    blocked_reason = _global_block_reason(current_user, project_id, route_result)
    step_results = _evaluate_steps(
        db,
        planned_steps,
        run_id=run_id,
        execution_mode=execution_mode,
        current_user=current_user,
        context=context,
        project_id=project_id,
        message=message,
        force_blocked_reason=blocked_reason,
    )
    dag_status = _run_status(step_results, blocked_reason, execution_mode)

    run = AgentDagRun(
        run_id=run_id,
        tenant_id=current_user.tenant_id,
        company_id=current_user.company_id,
        project_id=project_id,
        scope_type=current_user.scope_type.value if current_user.scope_type else "company",
        user_id=current_user.user_id,
        message=message,
        execution_mode=execution_mode,
        target_agent=route_result.get("target_agent"),
        status=dag_status,
        need_human_review=bool(route_result.get("need_human_review")),
        blocked_reason=blocked_reason,
        created_at=started_at,
        completed_at=_now(),
    )
    db.add(run)
    db.flush()

    for step_result in step_results:
        db.add(
            AgentDagStepRun(
                step_run_id=step_result["step_run_id"],
                run_id=run_id,
                step_id=step_result["step_id"],
                agent_code=step_result["agent_code"],
                action=step_result["action"],
                tool_name=step_result.get("tool_name"),
                status=step_result["status"],
                will_execute=step_result["will_execute"],
                requires_human_review=step_result.get("requires_human_review", False),
                input_summary=step_result.get("input_summary"),
                output_summary=step_result.get("output_summary"),
                error_message=step_result.get("error_message"),
                elapsed_ms=step_result.get("elapsed_ms"),
                created_at=started_at,
                completed_at=_now(),
            )
        )
    db.commit()

    return {
        **route_result,
        "execution_mode": execution_mode,
        "dag_status": dag_status,
        "dag_execution_allowed": execution_mode == "controlled_execute" and dag_status == "succeeded",
        "run_id": run_id,
        "blocked_reason": blocked_reason,
        "planned_steps": planned_steps,
        "step_results": step_results,
    }


def _global_block_reason(current_user: MockUser, project_id: str | None, route_result: dict[str, Any]) -> str | None:
    if route_result.get("blocked_actions"):
        return "restricted_action"
    try:
        assert_project_access(project_id, current_user)
    except PermissionError as exc:
        return str(exc)
    return None


def _evaluate_steps(
    db: Session,
    planned_steps: list[dict[str, Any]],
    *,
    run_id: str,
    execution_mode: AgentDagExecutionMode,
    current_user: MockUser,
    context: dict[str, Any],
    project_id: str | None,
    message: str,
    force_blocked_reason: str | None,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    step_statuses: dict[str, str] = {}
    for step in planned_steps:
        started = time.perf_counter()
        step_run_id = f"AGSTEP-{uuid.uuid4().hex[:16]}"
        status = "dry_run_passed"
        will_execute = False
        error_message = None
        output_summary = None
        approval_id = None

        blocked_dependency = _blocked_dependency(step, step_statuses)
        if blocked_dependency:
            status = "skipped"
            error_message = f"dependency {blocked_dependency} did not complete"
        elif force_blocked_reason:
            status = "blocked"
            error_message = force_blocked_reason
        elif _is_hazard_rectification_draft_step(step):
            enriched_context = _enriched_context(context, results)
            output_summary = draft_rectification_suggestion(
                db,
                message=message,
                context=enriched_context,
                current_user=current_user,
                llm_client=qwen if _hazard_llm_enhancement_enabled(enriched_context, execution_mode) else None,
            )
            status = "executed" if execution_mode == "controlled_execute" else "dry_run_passed"
            will_execute = execution_mode == "controlled_execute"
        elif step.get("tool_name"):
            try:
                normalized_tool_name = _tool_name(step["tool_name"])
                decision = evaluate_tool_access(
                    normalized_tool_name,
                    ToolExecutionContext(
                        execution_mode=execution_mode,
                        current_user=current_user,
                        project_id=project_id,
                    ),
                )
                if decision.status == "ready" and execution_mode == "controlled_execute":
                    tool_context = {**_enriched_context(context, results), "message": message, "query": message}
                    output_summary = _execute_read_only_tool(
                        db=db,
                        tool_name=normalized_tool_name,
                        current_user=current_user,
                        project_id=project_id,
                        context=tool_context,
                    )
                    status = "executed"
                    will_execute = True
                else:
                    status = "dry_run_passed" if decision.status == "ready" else decision.status
                    will_execute = False
                error_message = decision.reason
                if status == "approval_required" and execution_mode == "controlled_execute":
                    approval = create_approval_request_for_step(
                        db,
                        run_id=run_id,
                        step_run_id=step_run_id,
                        step=step,
                        tool_name=normalized_tool_name,
                        context=_enriched_context(context, results),
                        current_user=current_user,
                        reason=decision.reason,
                    )
                    approval_id = approval.approval_id
                    output_summary = {
                        "approval_id": approval.approval_id,
                        "requested_tool": approval.requested_tool,
                        "approval_status": approval.status,
                    }
            except UnknownAgentToolError as exc:
                status = "blocked"
                error_message = f"unknown tool: {exc.args[0]}"

        results.append(
            {
                "step_run_id": step_run_id,
                "step_id": step["step_id"],
                "agent_code": step["agent_code"],
                "action": step["action"],
                "tool_name": step.get("tool_name"),
                "status": status,
                "will_execute": will_execute,
                "requires_human_review": bool(step.get("requires_human_review")),
                "approval_id": approval_id,
                "input_summary": {"input_refs": step.get("input_refs", [])},
                "output_summary": output_summary,
                "error_message": error_message,
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
            }
        )
        step_statuses[step["step_id"]] = status
    return results


def _run_status(step_results: list[dict[str, Any]], blocked_reason: str | None, execution_mode: str) -> str:
    statuses = {step["status"] for step in step_results}
    if blocked_reason or "blocked" in statuses:
        return "blocked"
    if "approval_required" in statuses:
        return "approval_required"
    if execution_mode == "dry_run":
        return "dry_run_passed"
    if statuses <= {"executed", "dry_run_passed"}:
        return "succeeded"
    return "failed"


def _blocked_dependency(step: dict[str, Any], step_statuses: dict[str, str]) -> str | None:
    blocked_statuses = {"blocked", "failed", "approval_required", "skipped"}
    for dependency in step.get("depends_on", []):
        if step_statuses.get(dependency) in blocked_statuses:
            return dependency
    return None


def _hazard_llm_enhancement_enabled(context: dict[str, Any], execution_mode: str) -> bool:
    if execution_mode != "controlled_execute":
        return False
    if context.get("demo_mode") is True:
        return False
    return context.get("llm_enhance") is True


def _is_hazard_rectification_draft_step(step: dict[str, Any]) -> bool:
    return (
        step.get("agent_code") == "hazard_rectification_advisor"
        and step.get("action") == "draft_rectification_suggestion"
    )


def _enriched_context(context: dict[str, Any], step_results: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = dict(context)
    for step_result in step_results:
        output_summary = step_result.get("output_summary")
        if isinstance(output_summary, dict) and output_summary.get("proposed_work_order"):
            enriched.setdefault("title", output_summary["proposed_work_order"].get("title"))
            enriched.setdefault("description", output_summary["proposed_work_order"].get("description"))
            enriched.setdefault("work_order_type", output_summary["proposed_work_order"].get("work_order_type"))
            enriched.setdefault("priority", output_summary["proposed_work_order"].get("priority"))
            enriched.setdefault("source_type", output_summary["proposed_work_order"].get("source_type"))
            enriched.setdefault("source_id", output_summary["proposed_work_order"].get("source_id"))
        if isinstance(output_summary, dict) and output_summary.get("evidence"):
            enriched.setdefault("evidence_refs", output_summary["evidence"])
    return enriched


def _execute_read_only_tool(
    db: Session,
    *,
    tool_name: str,
    current_user: MockUser,
    project_id: str | None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if tool_name == "profile.read":
        return _read_profiles(db, current_user=current_user, project_id=project_id)
    if tool_name == "rules.read_triggers":
        return _read_rule_triggers(db, current_user=current_user, project_id=project_id)
    if tool_name == "work_orders.read":
        query = db.query(SafetyWorkOrder).filter(SafetyWorkOrder.company_id == current_user.company_id)
        if project_id:
            query = query.filter(SafetyWorkOrder.project_id == project_id)
        elif current_user.scope_type and current_user.scope_type.value == "project" and current_user.authorized_project_ids:
            query = query.filter(SafetyWorkOrder.project_id.in_(current_user.authorized_project_ids))
        row_count = query.limit(100).count()
        return {
            "row_count": row_count,
            "fields": ["work_order_id", "status", "priority"],
        }
    if tool_name == "hazards.read":
        hazard_id = (context or {}).get("hazard_id")
        return _read_hazards(
            db,
            current_user=current_user,
            project_id=project_id,
            hazard_id=hazard_id if isinstance(hazard_id, str) else None,
        )
    if tool_name == "metrics.read_catalog":
        return _read_metric_catalog(db, current_user=current_user, project_id=project_id)
    if tool_name == "knowledge.search":
        return _search_knowledge(db, current_user=current_user, context=context or {})
    if tool_name == "graph.read_neighbors":
        return _read_graph_neighbors(current_user=current_user, context=context or {})
    return {
        "row_count": 0,
        "fields": [],
        "note": f"{tool_name} validated as read-only; execution summary is not expanded in v1",
    }


def _read_profiles(db: Session, *, current_user: MockUser, project_id: str | None) -> dict[str, Any]:
    query = db.query(ProjectRiskProfile).filter(ProjectRiskProfile.company_id == current_user.company_id)
    if project_id:
        query = query.filter(ProjectRiskProfile.project_id == project_id)
    elif current_user.scope_type and current_user.scope_type.value == "project" and current_user.authorized_project_ids:
        query = query.filter(ProjectRiskProfile.project_id.in_(current_user.authorized_project_ids))
    rows = query.order_by(ProjectRiskProfile.calc_date.desc()).limit(20).all()
    fields = [
        "profile_type",
        "object_id",
        "project_id",
        "risk_score",
        "risk_level",
        "calculated_at",
        "confidence_level",
    ]
    return _summary(
        fields=fields,
        items=[
            {
                "profile_type": "project",
                "object_id": row.project_id,
                "project_id": row.project_id,
                "risk_score": row.total_risk_score,
                "risk_level": row.risk_level,
                "calculated_at": _date_to_string(row.calc_date),
                "confidence_level": row.confidence_level,
            }
            for row in rows
        ],
    )


def _read_rule_triggers(db: Session, *, current_user: MockUser, project_id: str | None) -> dict[str, Any]:
    query = db.query(RuleTriggerLog).filter(RuleTriggerLog.company_id == current_user.company_id)
    if project_id:
        query = query.filter(RuleTriggerLog.project_id == project_id)
    elif current_user.scope_type and current_user.scope_type.value == "project" and current_user.authorized_project_ids:
        query = query.filter(RuleTriggerLog.project_id.in_(current_user.authorized_project_ids))
    rows = query.order_by(RuleTriggerLog.created_at.desc()).limit(20).all()
    fields = ["rule_id", "object_type", "object_id", "project_id", "severity", "risk_action"]
    return _summary(
        fields=fields,
        items=[
            {
                "rule_id": row.rule_id,
                "object_type": row.object_type,
                "object_id": row.object_id,
                "project_id": row.project_id,
                "severity": row.severity,
                "risk_action": row.risk_action,
            }
            for row in rows
        ],
    )


def _read_hazards(
    db: Session,
    *,
    current_user: MockUser,
    project_id: str | None,
    hazard_id: str | None = None,
) -> dict[str, Any]:
    query = db.query(Hazard).filter(Hazard.company_id == current_user.company_id)
    if hazard_id:
        query = query.filter(Hazard.hazard_id == hazard_id)
    elif project_id:
        query = query.filter(Hazard.project_id == project_id)
    elif current_user.scope_type and current_user.scope_type.value == "project" and current_user.authorized_project_ids:
        query = query.filter(Hazard.project_id.in_(current_user.authorized_project_ids))
    rows = query.order_by(Hazard.created_at.desc()).limit(20).all()
    fields = [
        "hazard_id",
        "project_id",
        "hazard_type",
        "hazard_level",
        "status",
        "due_date",
        "is_major",
        "work_order_id",
        "attachment_count",
    ]
    return _summary(
        fields=fields,
        items=[
            {
                "hazard_id": row.hazard_id,
                "project_id": row.project_id,
                "hazard_type": row.hazard_type,
                "hazard_level": row.hazard_level,
                "status": row.status,
                "due_date": _date_to_string(row.due_date),
                "is_major": bool(row.is_major),
                "work_order_id": row.work_order_id,
                "attachment_count": _attachment_count(row.attachments),
            }
            for row in rows
        ],
    )


def _search_knowledge(
    db: Session,
    *,
    current_user: MockUser,
    context: dict[str, Any],
) -> dict[str, Any]:
    query = str(context.get("query") or context.get("message") or "").strip()
    if not query:
        return {
            "mode": "mysql_keyword",
            "query": "",
            "row_count": 0,
            "fields": ["collection", "record_id", "title", "content", "score"],
            "items": [],
            "evidence": [],
        }

    result = search_rag(
        db,
        tenant_id=current_user.tenant_id,
        query=query,
        top_k=context.get("top_k"),
        score_threshold=context.get("score_threshold"),
    )
    items = [
        {
            "collection": item["collection"],
            "record_id": item["record_id"],
            "title": item["title"],
            "content": str(item.get("content", ""))[:500],
            "score": item.get("score"),
        }
        for item in result.get("items", [])
    ]
    evidence = [
        {
            "type": "rag_hit",
            "collection": item["collection"],
            "record_id": item["record_id"],
            "score": str(item.get("score")),
        }
        for item in items
    ]
    return {
        "mode": result.get("mode"),
        "query": result.get("query"),
        "row_count": len(items),
        "fields": ["collection", "record_id", "title", "content", "score"],
        "items": items,
        "truncated": False,
        "evidence": evidence,
    }


def _read_graph_neighbors(*, current_user: MockUser, context: dict[str, Any]) -> dict[str, Any]:
    node_type = str(context.get("node_type") or "project")
    node_id = str(context.get("node_id") or context.get("project_id") or "").strip()
    if not node_id:
        return {
            "row_count": 0,
            "fields": ["relationship", "node_type", "node_id"],
            "items": [],
            "evidence": [],
            "note": "node_id is required",
        }

    client = build_neo4j_client_optional()
    if client is None:
        return {
            "row_count": 0,
            "fields": ["relationship", "node_type", "node_id"],
            "items": [],
            "evidence": [],
            "note": "neo4j_unavailable",
        }

    try:
        report = get_graph_neighbors(
            client,
            node_type=node_type,
            node_id=node_id,
            depth=1,
            current_user=current_user,
        )
    finally:
        client.close()

    if report is None:
        return {
            "row_count": 0,
            "fields": ["relationship", "node_type", "node_id"],
            "items": [],
            "evidence": [],
            "note": "node_not_found_or_not_accessible",
        }

    items = []
    evidence = []
    for neighbor in report.get("neighbors", []):
        props = neighbor.get("properties") or {}
        labels = neighbor.get("labels") or []
        node_label = labels[0].lower() if labels else neighbor.get("node_type")
        node_key = (
            props.get("project_id")
            or props.get("worker_id")
            or props.get("subcontractor_id")
            or props.get("hazard_id")
        )
        items.append(
            {
                "relationship": neighbor.get("relationship"),
                "node_type": node_label,
                "node_id": node_key,
                "properties": props,
            }
        )
        if node_key:
            evidence.append(
                {
                    "type": "graph_neighbor",
                    "relationship": neighbor.get("relationship"),
                    "node_type": node_label,
                    "node_id": node_key,
                }
            )

    return {
        "row_count": len(items),
        "fields": ["relationship", "node_type", "node_id"],
        "items": items,
        "truncated": False,
        "evidence": evidence,
        "anchor": report.get("anchor"),
    }


def _read_metric_catalog(db: Session, *, current_user: MockUser, project_id: str | None) -> dict[str, Any]:
    query = db.query(MetricCatalog).filter(MetricCatalog.company_id == current_user.company_id)
    if project_id:
        query = query.filter((MetricCatalog.project_id.is_(None)) | (MetricCatalog.project_id == project_id))
    elif current_user.scope_type and current_user.scope_type.value == "project" and current_user.authorized_project_ids:
        query = query.filter(
            (MetricCatalog.project_id.is_(None)) | (MetricCatalog.project_id.in_(current_user.authorized_project_ids))
        )
    rows = query.order_by(MetricCatalog.metric_code.asc()).limit(20).all()
    fields = [
        "metric_code",
        "metric_name",
        "business_definition",
        "calculation_formula",
        "source_tables",
        "source_fields",
        "aliases",
    ]
    return _summary(
        fields=fields,
        items=[
            {
                "metric_code": row.metric_code,
                "metric_name": row.metric_name,
                "business_definition": row.business_definition,
                "calculation_formula": row.calculation_formula,
                "source_tables": row.source_tables,
                "source_fields": row.source_fields,
                "aliases": row.aliases,
            }
            for row in rows
        ],
    )


def _summary(*, fields: list[str], items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "row_count": len(items),
        "fields": fields,
        "items": items,
        "truncated": False,
    }


def _date_to_string(value: Any) -> str | None:
    return value.isoformat() if value else None


def _attachment_count(attachments: dict | None) -> int:
    if not attachments:
        return 0
    if isinstance(attachments.get("items"), list):
        return len(attachments["items"])
    if isinstance(attachments.get("files"), list):
        return len(attachments["files"])
    return 0


def _tool_name(tool_name: str) -> str:
    if tool_name == "POST /api/v1/agent/nl2sql":
        return "nl2sql.audit_only"
    return tool_name


def _now() -> dt.datetime:
    return dt.datetime.utcnow()
