"""Generate tests/datasets/memory_context_55.jsonl with 55+ multi-turn context cases."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "tests" / "datasets" / "memory_context_55.jsonl"


def _session_case(
    case_id: str,
    category: str,
    session_id: str,
    turns: list[dict],
    expected_resolved_context: dict,
    *,
    expected_message_count: int | None = None,
    expected_summary_fragment: str | None = None,
    forbidden_context_keys: list[str] | None = None,
    difficulty: str = "easy",
) -> dict:
    return {
        "case_id": case_id,
        "category": category,
        "flow": "session_memory",
        "session_id": session_id,
        "turns": turns,
        "expected_resolved_context": expected_resolved_context,
        "expected_message_count": expected_message_count or len(turns),
        "expected_summary_fragment": expected_summary_fragment,
        "forbidden_context_keys": forbidden_context_keys or [],
        "difficulty": difficulty,
    }


def _user_turn(content: str, context: dict | None = None) -> dict:
    return {"message": {"role": "user", "content": content}, "context": context or {}}


def _assistant_turn(content: str, context: dict, summary: str | None = None) -> dict:
    turn = {"message": {"role": "assistant", "content": content}, "context": context}
    if summary:
        turn["summary"] = summary
    return turn


def build_cases() -> list[dict]:
    cases: list[dict] = []

    for index in range(1, 13):
        project_id = f"P{index:03d}"
        cases.append(
            _session_case(
                f"MEM-PROJ-{index:03d}",
                "project_reference",
                f"bench-proj-{index:03d}",
                [
                    _user_turn(f"查看 {project_id} 项目风险画像", {"project_id": project_id}),
                    _assistant_turn(
                        f"{project_id} 当前 risk_level=high",
                        {"project_id": project_id, "risk_level": "high"},
                        summary=f"{project_id} 高风险项目",
                    ),
                    _user_turn("这个项目的工单状态如何？"),
                ],
                {"project_id": project_id},
                expected_summary_fragment=project_id,
            )
        )

    for index in range(1, 11):
        hazard_id = f"H{index:03d}"
        project_id = f"P{index:03d}"
        cases.append(
            _session_case(
                f"MEM-HAZ-{index:03d}",
                "hazard_reference",
                f"bench-haz-{index:03d}",
                [
                    _user_turn(f"分析隐患 {hazard_id} 的整改证据", {"hazard_id": hazard_id, "project_id": project_id}),
                    _assistant_turn(
                        f"{hazard_id} 属于临边防护类隐患",
                        {"hazard_id": hazard_id, "project_id": project_id, "hazard_type": "edge_protection"},
                    ),
                    _user_turn("继续说明它的闭环要求"),
                ],
                {"hazard_id": hazard_id, "project_id": project_id},
            )
        )

    for index in range(1, 11):
        work_order_id = f"WO-DEMO-P{index:03d}-001"
        cases.append(
            _session_case(
                f"MEM-WO-{index:03d}",
                "work_order_reference",
                f"bench-wo-{index:03d}",
                [
                    _user_turn(f"检查工单 {work_order_id} 是否超期", {"work_order_id": work_order_id}),
                    _assistant_turn(
                        f"{work_order_id} 当前状态 pending_confirm",
                        {"work_order_id": work_order_id, "status": "pending_confirm"},
                    ),
                    _user_turn("这个工单下一步合法动作是什么？"),
                ],
                {"work_order_id": work_order_id},
            )
        )

    metric_codes = [
        "M-PROJ-RISK-SCORE",
        "M-PROJ-HIGH-RISK-COUNT",
        "M-WORKER-CERT-EXPIRED",
        "M-HAZARD-OPEN-COUNT",
        "M-WO-OVERDUE-RATE",
        "M-RULE-TRIGGER-COUNT",
        "M-SUBCON-PENALTY-RATE",
        "M-PROJ-SCHEDULE-PRESSURE",
        "M-DEVICE-INSPECTION-DUE",
        "M-TRAINING-COMPLETION",
    ]
    for index, metric_code in enumerate(metric_codes, start=1):
        cases.append(
            _session_case(
                f"MEM-MET-{index:03d}",
                "metric_reference",
                f"bench-met-{index:03d}",
                [
                    _user_turn(f"解释指标 {metric_code} 的业务含义", {"metric_code": metric_code}),
                    _assistant_turn(
                        f"{metric_code} 用于风险排名统计",
                        {"metric_code": metric_code, "metric_domain": "risk"},
                    ),
                    _user_turn("上次这个指标对应哪些项目？"),
                ],
                {"metric_code": metric_code},
            )
        )

    rule_ids = [
        "SR-PROJ-001",
        "SR-PROJ-004",
        "SR-WORKER-001",
        "SR-WORKER-002",
        "SR-WORKER-004",
        "SR-WORKER-005",
        "SR-SUB-001",
        "SR-SUB-002",
    ]
    for index, rule_id in enumerate(rule_ids, start=1):
        cases.append(
            _session_case(
                f"MEM-RULE-{index:03d}",
                "rule_reference",
                f"bench-rule-{index:03d}",
                [
                    _user_turn(f"{rule_id} 为什么触发？", {"rule_id": rule_id}),
                    _assistant_turn(
                        f"{rule_id} 因超期未闭环触发",
                        {"rule_id": rule_id, "trigger_reason": "overdue"},
                    ),
                    _user_turn("把这条规则关联的工单列出来"),
                ],
                {"rule_id": rule_id},
            )
        )

    for index in range(1, 9):
        project_id = f"P{index:03d}"
        hazard_id = f"H{index:03d}"
        work_order_id = f"WO-DEMO-P{index:03d}-001"
        cases.append(
            _session_case(
                f"MEM-MULTI-{index:03d}",
                "multi_entity",
                f"bench-multi-{index:03d}",
                [
                    _user_turn(
                        f"联动查看 {project_id}、{hazard_id} 和 {work_order_id}",
                        {
                            "project_id": project_id,
                            "hazard_id": hazard_id,
                            "work_order_id": work_order_id,
                        },
                    ),
                    _assistant_turn(
                        "已聚合项目、隐患和工单上下文",
                        {
                            "project_id": project_id,
                            "hazard_id": hazard_id,
                            "work_order_id": work_order_id,
                            "intent": "rectification",
                        },
                    ),
                    _user_turn("基于这些上下文给出整改建议"),
                ],
                {
                    "project_id": project_id,
                    "hazard_id": hazard_id,
                    "work_order_id": work_order_id,
                },
                difficulty="medium",
            )
        )

    for index in range(1, 13):
        project_id = f"P{index:03d}"
        cases.append(
            _session_case(
                f"MEM-PRON-{index:03d}",
                "pronoun_follow_up",
                f"bench-pron-{index:03d}",
                [
                    _user_turn("最近高风险项目有哪些？", {"intent": "nl2sql"}),
                    _assistant_turn(
                        f"排名首位是 {project_id}",
                        {"project_id": project_id, "risk_level": "high"},
                        summary=f"top project {project_id}",
                    ),
                    _user_turn("它的风险驱动因素是什么？"),
                ],
                {"project_id": project_id},
                difficulty="medium",
            )
        )

    clarification_templates = [
        ("Show recent risky projects", "please provide a time range", ["最近30天"]),
        ("List overdue work orders", "which project scope should be used", ["P001"]),
        ("Count open hazards", "specify hazard severity", ["major hazards only"]),
        ("Top subcontractors by penalty", "confirm ranking metric", ["按处罚次数"]),
        ("Worker cert expiry trend", "provide worker scope", ["特种作业人员"]),
        ("Project schedule pressure", "confirm time window", ["本周"]),
        ("Rule trigger summary", "specify rule family", ["SR-PROJ rules"]),
        ("Device inspection backlog", "confirm device type", ["塔吊"]),
        ("Training completion rate", "confirm org scope", ["项目级"]),
        ("High risk project ranking", "confirm risk threshold", ["risk_level=high"]),
    ]
    for index, (question, prompt, replies) in enumerate(clarification_templates, start=1):
        turns = [
            {
                "original_question": question,
                "clarification_prompt": prompt,
                "audit_id": f"NLSQL-BENCH-{index:03d}",
            }
        ]
        for reply in replies:
            turns.append({"reply": reply})
        cases.append(
            {
                "case_id": f"MEM-CLR-{index:03d}",
                "category": "nl2sql_clarification",
                "flow": "clarification",
                "session_id": f"bench-clr-{index:03d}",
                "turns": turns,
                "expected_resolved_context": {
                    "original_question": question,
                    "clarification_prompt": prompt,
                },
                "expected_refined_fragments": [question, prompt, replies[-1]],
                "expected_turn": 1 + len(replies),
                "difficulty": "medium",
            }
        )

    for index in range(1, 6):
        project_id = f"P{index:03d}"
        turns = [
            _user_turn(f"查看 {project_id}", {"project_id": project_id, "full_sql_result": [{"drop": "me"}]}),
            _assistant_turn("已过滤敏感结果", {"project_id": project_id}),
            _user_turn("继续分析这个项目"),
        ]
        cases.append(
            _session_case(
                f"MEM-SAFE-{index:03d}",
                "context_sanitization",
                f"bench-safe-{index:03d}",
                turns,
                {"project_id": project_id},
                forbidden_context_keys=["full_sql_result", "raw_video", "identity_card"],
            )
        )

    return cases


def main() -> None:
    cases = build_cases()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        "\n".join(json.dumps(case, ensure_ascii=False) for case in cases) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(cases)} cases to {OUTPUT}")


if __name__ == "__main__":
    main()
