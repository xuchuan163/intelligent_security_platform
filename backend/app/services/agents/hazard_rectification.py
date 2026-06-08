from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.core.security import MockUser, apply_data_scope, assert_project_access
from app.infrastructure.database.models import Hazard, RuleTriggerLog, SafetyWorkOrder
from app.services.agents.prompt_registry import get_active_prompt_version


_RECTIFICATION_MEASURES: dict[str, list[str]] = {
    "edge_protection": [
        "立即补设双层防护栏杆并固定牢固",
        "划定临边警戒区域并设置警示标识",
        "安排专人监护，禁止无关人员进入作业面",
    ],
    "scaffold": [
        "暂停相关作业并封闭危险脚手架区域",
        "组织架体验收并补齐连墙件、扫地杆和挡脚板",
        "整改完成后重新办理验收再恢复作业",
    ],
    "fire": [
        "清理可燃物并补齐灭火器、消防水源",
        "落实动火监护和动火票管理",
        "开展现场防火巡查直至风险消除",
    ],
}

_DEFAULT_MEASURES = [
    "立即停止危险作业并设置警戒区域",
    "明确责任分包与整改时限",
    "整改完成后组织复查并留存影像证据",
]

_HAZARD_TYPE_ALIASES: dict[str, str] = {
    "临边防护": "edge_protection",
    "脚手架": "scaffold",
    "消防": "fire",
    "高处作业": "edge_protection",
    "基坑": "scaffold",
}

_REVIEW_CHECKPOINTS = [
    "整改前后影像证据齐全",
    "责任人和复查人明确",
    "关联工单状态可追踪",
    "重大隐患已升级督办",
]


def load_hazard_evidence_bundle(
    db: Session,
    *,
    hazard_id: str | None,
    project_id: str | None,
    current_user: MockUser,
) -> dict[str, Any]:
    assert_project_access(project_id, current_user)

    hazard_query = apply_data_scope(db.query(Hazard), Hazard, current_user)
    if hazard_id:
        hazard_query = hazard_query.filter(Hazard.hazard_id == hazard_id)
    elif project_id:
        hazard_query = hazard_query.filter(Hazard.project_id == project_id)
    hazard = hazard_query.order_by(Hazard.created_at.desc()).first()

    work_order = None
    if hazard and hazard.work_order_id:
        work_order = (
            apply_data_scope(db.query(SafetyWorkOrder), SafetyWorkOrder, current_user)
            .filter(SafetyWorkOrder.work_order_id == hazard.work_order_id)
            .first()
        )

    trigger_query = apply_data_scope(db.query(RuleTriggerLog), RuleTriggerLog, current_user)
    if hazard:
        trigger_query = trigger_query.filter(RuleTriggerLog.project_id == hazard.project_id)
    elif project_id:
        trigger_query = trigger_query.filter(RuleTriggerLog.project_id == project_id)
    rule_triggers = trigger_query.order_by(RuleTriggerLog.created_at.desc()).limit(5).all()

    return {
        "hazard": _hazard_to_dict(hazard) if hazard else None,
        "work_order": _work_order_to_dict(work_order) if work_order else None,
        "rule_triggers": [_rule_trigger_to_dict(row) for row in rule_triggers],
    }


def build_evidence_refs(bundle: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    hazard = bundle.get("hazard")
    if isinstance(hazard, dict) and hazard.get("hazard_id"):
        refs.append(
            {
                "ref_type": "hazard",
                "ref_id": hazard["hazard_id"],
                "label": f"隐患 {hazard['hazard_id']} · {hazard.get('hazard_type', 'unknown')}",
            }
        )
    work_order = bundle.get("work_order")
    if isinstance(work_order, dict) and work_order.get("work_order_id"):
        refs.append(
            {
                "ref_type": "work_order",
                "ref_id": work_order["work_order_id"],
                "label": f"工单 {work_order['work_order_id']} · {work_order.get('status', 'unknown')}",
            }
        )
    for trigger in bundle.get("rule_triggers") or []:
        if not isinstance(trigger, dict) or not trigger.get("rule_id"):
            continue
        refs.append(
            {
                "ref_type": "rule_trigger",
                "ref_id": trigger["rule_id"],
                "label": f"规则 {trigger['rule_id']} · {trigger.get('severity', 'unknown')}",
            }
        )
    return refs


def draft_rectification_suggestion(
    db: Session,
    *,
    message: str,
    context: dict[str, Any] | None,
    current_user: MockUser,
    llm_client: Any | None = None,
) -> dict[str, Any]:
    context = context or {}
    hazard_id = context.get("hazard_id")
    project_id = context.get("project_id")
    bundle = load_hazard_evidence_bundle(
        db,
        hazard_id=hazard_id if isinstance(hazard_id, str) else None,
        project_id=project_id if isinstance(project_id, str) else None,
        current_user=current_user,
    )
    evidence_refs = build_evidence_refs(bundle)
    rag_refs = context.get("evidence_refs") or []
    if isinstance(rag_refs, list):
        evidence_refs.extend(ref for ref in rag_refs if isinstance(ref, dict) and ref not in evidence_refs)
    hazard = bundle.get("hazard")
    if hazard is None:
        return {
            "status": "hazard_not_found",
            "rectification_suggestions": [],
            "review_checkpoints": [],
            "evidence": evidence_refs,
            "need_human_review": True,
            "message": "未找到可引用的隐患证据，请提供有效的 hazard_id 或 project_id。",
        }

    suggestions = _deterministic_suggestions(hazard)
    result = {
        "status": "generated",
        "hazard_id": hazard["hazard_id"],
        "project_id": hazard.get("project_id"),
        "existing_work_order_id": hazard.get("work_order_id"),
        "rectification_suggestions": suggestions,
        "review_checkpoints": list(_REVIEW_CHECKPOINTS),
        "evidence": evidence_refs,
        "need_human_review": True,
        "llm_enhanced": False,
        "proposed_work_order": _proposed_work_order_payload(hazard, suggestions, context),
    }

    llm_result = _try_llm_enhancement(db, message=message, bundle=bundle, evidence_refs=evidence_refs, llm_client=llm_client)
    if llm_result is not None:
        result.update(llm_result)
        result["llm_enhanced"] = True
    return result


def _normalize_hazard_type(hazard_type: str | None) -> str:
    raw = str(hazard_type or "").strip()
    if not raw:
        return ""
    if raw in _HAZARD_TYPE_ALIASES:
        return _HAZARD_TYPE_ALIASES[raw]
    return raw.lower()


def _deterministic_suggestions(hazard: dict[str, Any]) -> list[str]:
    hazard_type = _normalize_hazard_type(hazard.get("hazard_type"))
    measures = _RECTIFICATION_MEASURES.get(hazard_type, _DEFAULT_MEASURES)
    suggestions = list(measures)
    if hazard.get("is_major"):
        suggestions.append("按重大隐患流程升级至项目安全负责人督办")
    if hazard.get("due_date"):
        suggestions.append(f"在 {hazard['due_date']} 前完成整改并提交复查")
    return suggestions


def _proposed_work_order_payload(
    hazard: dict[str, Any],
    suggestions: list[str],
    context: dict[str, Any],
) -> dict[str, Any] | None:
    if not context.get("propose_work_order"):
        return None
    if hazard.get("work_order_id"):
        return None
    title = context.get("title") or f"隐患整改 · {hazard.get('hazard_type', 'hazard')}"
    description = context.get("description") or "；".join(suggestions[:3])
    return {
        "work_order_type": "hazard_rectification",
        "title": title,
        "description": description,
        "project_id": hazard.get("project_id"),
        "source_type": "hazard",
        "source_id": hazard.get("hazard_id"),
        "priority": "high" if hazard.get("is_major") else "normal",
    }


def _try_llm_enhancement(
    db: Session,
    *,
    message: str,
    bundle: dict[str, Any],
    evidence_refs: list[dict[str, str]],
    llm_client: Any | None,
) -> dict[str, Any] | None:
    if llm_client is None:
        return None
    prompt = get_active_prompt_version(db, "hazard_rectification_advisor")
    if prompt is None:
        return None

    with open(prompt.prompt_path, "r", encoding="utf-8") as file:
        prompt_text = file.read()

    response = llm_client.chat(
        [
            {
                "role": "system",
                "content": (
                    f"{prompt_text}\n\n"
                    "Return one JSON object with keys: rectification_suggestions, review_checkpoints, "
                    "evidence, need_human_review. evidence must cite hazard/work_order/rule IDs from input."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "message": message,
                        "hazard_evidence": bundle,
                        "evidence_refs": evidence_refs,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        temperature=0.0,
    )
    if not response.get("available", False):
        return None
    parsed = _parse_json_object(response.get("content"))
    if parsed is None:
        return None
    return {
        "rectification_suggestions": parsed.get("rectification_suggestions") or [],
        "review_checkpoints": parsed.get("review_checkpoints") or list(_REVIEW_CHECKPOINTS),
        "evidence": parsed.get("evidence") or evidence_refs,
        "need_human_review": bool(parsed.get("need_human_review", True)),
    }


def _parse_json_object(content: Any) -> dict[str, Any] | None:
    if not isinstance(content, str) or not content.strip():
        return None
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _hazard_to_dict(hazard: Hazard) -> dict[str, Any]:
    return {
        "hazard_id": hazard.hazard_id,
        "project_id": hazard.project_id,
        "hazard_type": hazard.hazard_type,
        "hazard_level": hazard.hazard_level,
        "description": hazard.description,
        "status": hazard.status,
        "due_date": hazard.due_date.isoformat() if hazard.due_date else None,
        "is_major": bool(hazard.is_major),
        "work_order_id": hazard.work_order_id,
        "location": hazard.location,
    }


def _work_order_to_dict(work_order: SafetyWorkOrder) -> dict[str, Any]:
    return {
        "work_order_id": work_order.work_order_id,
        "project_id": work_order.project_id,
        "status": work_order.status,
        "priority": work_order.priority,
        "title": work_order.title,
        "work_order_type": work_order.work_order_type,
    }


def _rule_trigger_to_dict(trigger: RuleTriggerLog) -> dict[str, Any]:
    return {
        "rule_id": trigger.rule_id,
        "object_type": trigger.object_type,
        "object_id": trigger.object_id,
        "project_id": trigger.project_id,
        "severity": trigger.severity,
        "risk_action": trigger.risk_action,
    }
