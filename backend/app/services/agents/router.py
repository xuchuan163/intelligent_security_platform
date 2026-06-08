from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.infrastructure.llm.qwen_client import qwen
from app.services.agents.prompt_registry import get_active_prompt_version


RESTRICTED_ACTION_KEYWORDS = (
    "停工",
    "处罚",
    "罚款",
    "清退",
    "开除",
    "辞退",
    "限制作业",
    "disciplinary",
    "penalty",
    "remove subcontractor",
    "stop work",
)


def route_agent_message(
    db: Session,
    message: str,
    context: dict[str, Any] | None = None,
    execution_mode: str = "route_only",
    llm_client: Any | None = None,
) -> dict[str, Any]:
    normalized = message.lower()
    intent, target_agent, reason = _classify_message(normalized, message, context)
    prompt = get_active_prompt_version(db, target_agent)
    blocked_actions = _blocked_actions(normalized, message)

    merged_context = dict(context or {})
    merged_context.setdefault("message", message)
    result = {
        "intent": intent,
        "target_agent": target_agent,
        "prompt_version": prompt.prompt_version if prompt else None,
        "prompt_hash": prompt.prompt_hash if prompt else None,
        "route_reason": reason,
        "execution_mode": execution_mode,
        "need_human_review": bool(blocked_actions),
        "blocked_actions": blocked_actions,
        "context": merged_context,
    }
    if execution_mode == "execute_preview":
        result.update(_execute_preview(message, context or {}, result, prompt, llm_client or qwen))
    if execution_mode == "plan_only":
        result.update(
            {
                "dag_status": "planned",
                "dag_execution_allowed": False,
                "planned_steps": _build_planned_steps(result),
            }
        )
    return result


def _classify_message(
    normalized: str,
    original: str,
    context: dict[str, Any] | None = None,
) -> tuple[str, str, str]:
    if (context or {}).get("hazard_id") and _contains_any(
        normalized, original, ("隐患", "整改", "hazard", "rectification", "复查")
    ):
        return (
            "hazard_rectification",
            "hazard_rectification_advisor",
            "hazard context and rectification intent take priority",
        )
    if _contains_any(normalized, original, ("工单", "work order", "wo", "闭环", "超期", "派发", "接单")):
        return "work_order", "work_order_coordinator", "message mentions work order lifecycle"
    if _contains_any(normalized, original, ("sr-", "规则", "rule", "合规", "触发")):
        return "rule_compliance", "rule_compliance_checker", "message mentions rule or compliance evidence"
    if _contains_any(normalized, original, ("隐患", "整改", "hazard", "rectification", "复查")):
        return "hazard_rectification", "hazard_rectification_advisor", "message mentions hazard rectification"
    if _contains_any(normalized, original, ("查询", "统计", "排名", "top", "多少", "count", "list", "sql", "指标")):
        return "nl2sql", "nl2sql_analyst", "message asks for data query or metric retrieval"
    if _contains_any(normalized, original, ("画像", "风险分", "风险等级", "profile", "risk score", "risk level")):
        return "risk_profile", "risk_profile_analyst", "message asks about risk profile explanation"
    return "general_safety", "safety_supervisor", "message needs general safety routing"


def _contains_any(normalized: str, original: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in normalized or keyword in original for keyword in keywords)


def _blocked_actions(normalized: str, original: str) -> list[str]:
    if _contains_any(normalized, original, RESTRICTED_ACTION_KEYWORDS):
        return ["restricted_action"]
    return []


def _build_planned_steps(route_result: dict[str, Any]) -> list[dict[str, Any]]:
    needs_review = bool(route_result.get("need_human_review"))
    target_agent = route_result["target_agent"]
    steps = [
        _planned_step(
            step_id="step_1",
            agent_code="safety_supervisor",
            action="classify_intent_and_route",
            depends_on=[],
            input_refs=["message", "context"],
            output_key="route",
            requires_human_review=False,
        )
    ]

    branch_steps = {
        "nl2sql_analyst": [
            _planned_step(
                step_id="step_2",
                agent_code="nl2sql_analyst",
                action="load_metric_semantic_context",
                depends_on=["step_1"],
                input_refs=["route", "message", "context"],
                output_key="metric_context",
                requires_human_review=False,
                tool_name="metrics.read_catalog",
            ),
            _planned_step(
                step_id="step_3",
                agent_code="nl2sql_analyst",
                action="prepare_guarded_nl2sql_request",
                depends_on=["step_2"],
                input_refs=["metric_context", "message", "context"],
                output_key="nl2sql_gate_request",
                requires_human_review=needs_review,
                tool_name="POST /api/v1/agent/nl2sql",
            )
        ],
        "hazard_rectification_advisor": [
            _planned_step(
                step_id="step_2",
                agent_code="hazard_rectification_advisor",
                action="collect_hazard_evidence",
                depends_on=["step_1"],
                input_refs=["route", "context.project_id", "context.hazard_id"],
                output_key="hazard_evidence",
                requires_human_review=False,
                tool_name="hazards.read",
            ),
            _planned_step(
                step_id="step_3",
                agent_code="hazard_rectification_advisor",
                action="search_knowledge_evidence",
                depends_on=["step_2"],
                input_refs=["hazard_evidence", "message"],
                output_key="knowledge_evidence",
                requires_human_review=False,
                tool_name="knowledge.search",
            ),
            _planned_step(
                step_id="step_4",
                agent_code="hazard_rectification_advisor",
                action="draft_rectification_suggestion",
                depends_on=["step_2", "step_3"],
                input_refs=["hazard_evidence", "knowledge_evidence", "message"],
                output_key="rectification_suggestion",
                requires_human_review=needs_review,
            ),
        ],
        "work_order_coordinator": [
            _planned_step(
                step_id="step_2",
                agent_code="work_order_coordinator",
                action="inspect_work_order_state",
                depends_on=["step_1"],
                input_refs=["route", "context.work_order_id", "context.project_id"],
                output_key="work_order_state",
                requires_human_review=False,
                tool_name="work_orders.read",
            ),
            _planned_step(
                step_id="step_3",
                agent_code="work_order_coordinator",
                action="identify_next_legal_action",
                depends_on=["step_2"],
                input_refs=["work_order_state", "message"],
                output_key="work_order_action_preview",
                requires_human_review=needs_review,
            ),
        ],
        "rule_compliance_checker": [
            _planned_step(
                step_id="step_2",
                agent_code="rule_compliance_checker",
                action="collect_rule_trigger_evidence",
                depends_on=["step_1"],
                input_refs=["route", "context.rule_id", "context.project_id"],
                output_key="rule_evidence",
                requires_human_review=False,
                tool_name="rules.read_triggers",
            ),
            _planned_step(
                step_id="step_3",
                agent_code="rule_compliance_checker",
                action="explain_rule_trigger",
                depends_on=["step_2"],
                input_refs=["rule_evidence", "message"],
                output_key="rule_explanation",
                requires_human_review=needs_review,
            ),
        ],
        "risk_profile_analyst": [
            _planned_step(
                step_id="step_2",
                agent_code="risk_profile_analyst",
                action="load_profile_evidence",
                depends_on=["step_1"],
                input_refs=["route", "context.project_id", "context.worker_id", "context.subcontractor_id"],
                output_key="profile_evidence",
                requires_human_review=False,
                tool_name="profile.read",
            ),
            _planned_step(
                step_id="step_3",
                agent_code="risk_profile_analyst",
                action="explain_risk_drivers",
                depends_on=["step_2"],
                input_refs=["profile_evidence", "message"],
                output_key="risk_driver_explanation",
                requires_human_review=needs_review,
            ),
        ],
        "safety_supervisor": [
            _planned_step(
                step_id="step_2",
                agent_code="safety_supervisor",
                action="draft_general_safety_response_plan",
                depends_on=["step_1"],
                input_refs=["route", "message", "context"],
                output_key="safety_response_plan",
                requires_human_review=needs_review,
            )
        ],
    }
    steps.extend(branch_steps.get(target_agent, branch_steps["safety_supervisor"]))

    if target_agent == "hazard_rectification_advisor" and _needs_hazard_work_order_proposal(route_result):
        steps.append(
            _planned_step(
                step_id=f"step_{len(steps) + 1}",
                agent_code="hazard_rectification_advisor",
                action="propose_rectification_work_order",
                depends_on=[steps[-1]["step_id"]],
                input_refs=["rectification_suggestion", "context.hazard_id", "context.propose_work_order"],
                output_key="work_order_proposal",
                requires_human_review=True,
                tool_name="work_orders.create",
            )
        )

    if target_agent == "work_order_coordinator" and _needs_work_order_transition_approval(route_result):
        steps.append(
            _planned_step(
                step_id=f"step_{len(steps) + 1}",
                agent_code="work_order_coordinator",
                action="request_work_order_transition_approval",
                depends_on=[steps[-1]["step_id"]],
                input_refs=["work_order_state", "context.work_order_id", "context.action"],
                output_key="work_order_transition_approval",
                requires_human_review=True,
                tool_name="work_orders.transition",
            )
        )

    if needs_review and not any(step["requires_human_review"] for step in steps):
        steps.append(
            _planned_step(
                step_id=f"step_{len(steps) + 1}",
                agent_code="safety_supervisor",
                action="request_human_review",
                depends_on=[steps[-1]["step_id"]],
                input_refs=[steps[-1]["output_key"], "blocked_actions"],
                output_key="human_review_request",
                requires_human_review=True,
            )
        )
    return steps


def _needs_hazard_work_order_proposal(route_result: dict[str, Any]) -> bool:
    context = route_result.get("context") or {}
    if context.get("propose_work_order"):
        return True
    message = str(context.get("message") or "")
    return _contains_any(
        message.lower(),
        message,
        ("生成工单", "创建工单", "开单", "work order", "create work order"),
    )


def _needs_work_order_transition_approval(route_result: dict[str, Any]) -> bool:
    context = route_result.get("context") or {}
    if not context.get("work_order_id"):
        return False
    text = f"{route_result.get('route_reason', '')} {context.get('action', '')}".lower()
    return _contains_any(
        text,
        text,
        (
            "dispatch",
            "confirm",
            "transition",
            "accept",
            "close",
            "review_pass",
            "review_reject",
            "submit_result",
        ),
    )


def _planned_step(
    step_id: str,
    agent_code: str,
    action: str,
    depends_on: list[str],
    input_refs: list[str],
    output_key: str,
    requires_human_review: bool,
    tool_name: str | None = None,
) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "agent_code": agent_code,
        "action": action,
        "depends_on": depends_on,
        "input_refs": input_refs,
        "output_key": output_key,
        "requires_human_review": requires_human_review,
        "will_execute": False,
        "tool_name": tool_name,
    }


def _execute_preview(
    message: str,
    context: dict[str, Any],
    route_result: dict[str, Any],
    prompt,
    llm_client: Any,
) -> dict[str, Any]:
    if prompt is None:
        return {
            "preview_status": "prompt_missing",
            "llm_available": False,
            "llm_message": "active prompt not found",
            "llm_preview": None,
        }

    prompt_text = _read_prompt_text(prompt.prompt_path)
    response = llm_client.chat(
        [
            {
                "role": "system",
                "content": _build_controller_prompt(prompt_text, route_result),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "message": message,
                        "context": context,
                        "deterministic_route": route_result,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.0,
    )
    if not response.get("available", False):
        return {
            "preview_status": "llm_unavailable",
            "llm_available": False,
            "llm_message": response.get("message"),
            "llm_preview": None,
        }

    content = response.get("content")
    parsed = _parse_preview_json(content)
    if parsed is None:
        return {
            "preview_status": "invalid_llm_output",
            "llm_available": True,
            "llm_message": response.get("message"),
            "llm_preview": None,
        }

    if route_result["need_human_review"]:
        parsed["need_human_review"] = True
    return {
        "preview_status": "generated",
        "llm_available": True,
        "llm_message": response.get("message"),
        "llm_preview": parsed,
    }


def _read_prompt_text(prompt_path: str) -> str:
    with open(prompt_path, "r", encoding="utf-8") as file:
        return file.read()


def _build_controller_prompt(prompt_text: str, route_result: dict[str, Any]) -> str:
    return (
        f"{prompt_text}\n\n"
        "You are generating a route preview only. Do not execute tools, SQL, DAGs, or work orders.\n"
        "Return one JSON object with keys: route_explanation, expected_inputs, evidence_needed, "
        "safety_notes, need_human_review.\n"
        f"Deterministic route must not be changed: {json.dumps(route_result, ensure_ascii=False)}"
    )


def _parse_preview_json(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed
