from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class RuleCondition:
    field: str
    operator: str
    value: Any


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    object_type: str
    rule_name: str
    severity: str
    risk_tag: str
    condition: RuleCondition | list[RuleCondition]
    risk_bonus: float
    suggested_work_order_type: str | None = None
    work_order_title_template: str | None = None
    work_order_priority: str = "normal"
    auto_create_work_order: bool = False


@dataclass(frozen=True)
class RuleTrigger:
    rule_id: str
    rule_name: str
    object_type: str
    severity: str
    risk_tag: str
    risk_bonus: float
    suggested_work_order_type: str | None
    work_order_title_template: str | None
    work_order_priority: str
    auto_create_work_order: bool
    evidence: dict[str, Any]


class RuleEngine:
    """Small YAML-backed strong-rule engine for MVP profile calculations."""

    def __init__(self, rules: list[RuleDefinition]) -> None:
        self.rules = rules

    @classmethod
    def from_config(cls, config_dir: Path | None = None) -> "RuleEngine":
        root = Path(__file__).resolve().parents[4]
        rules_dir = config_dir or root / "config" / "rules"
        rules: list[RuleDefinition] = []

        for path in sorted(rules_dir.glob("*_rules.yaml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for item in payload.get("rules", []):
                condition = _parse_condition(item["condition"])
                action = item.get("action", {})
                rules.append(
                    RuleDefinition(
                        rule_id=item["rule_id"],
                        object_type=item["object_type"],
                        rule_name=item["rule_name"],
                        severity=item["severity"],
                        risk_tag=item.get("risk_tag") or item["rule_name"],
                        condition=condition,
                        risk_bonus=float(action.get("risk_bonus", 0)),
                        suggested_work_order_type=action.get("suggested_work_order_type"),
                        work_order_title_template=action.get("work_order_title_template"),
                        work_order_priority=action.get("work_order_priority", "normal"),
                        auto_create_work_order=bool(action.get("auto_create_work_order", False)),
                    )
                )

        return cls(rules)

    def evaluate(self, object_type: str, facts: dict[str, Any]) -> list[RuleTrigger]:
        triggered: list[RuleTrigger] = []
        for rule in self.rules:
            if rule.object_type != object_type:
                continue
            if not _condition_matches(rule.condition, facts):
                continue
            evidence = _evidence_for(rule.condition, facts)
            triggered.append(
                RuleTrigger(
                    rule_id=rule.rule_id,
                    rule_name=rule.rule_name,
                    object_type=rule.object_type,
                    severity=rule.severity,
                    risk_tag=rule.risk_tag,
                    risk_bonus=rule.risk_bonus,
                    suggested_work_order_type=rule.suggested_work_order_type,
                    work_order_title_template=rule.work_order_title_template,
                    work_order_priority=rule.work_order_priority,
                    auto_create_work_order=rule.auto_create_work_order,
                    evidence=evidence,
                )
            )
        return triggered


def _parse_condition(raw: dict[str, Any]) -> RuleCondition | list[RuleCondition]:
    if "all" in raw:
        return [_parse_single_condition(item) for item in raw["all"]]
    return _parse_single_condition(raw)


def _parse_single_condition(raw: dict[str, Any]) -> RuleCondition:
    return RuleCondition(
        field=raw["field"],
        operator=raw["operator"],
        value=raw.get("value"),
    )


def _condition_matches(condition: RuleCondition | list[RuleCondition], facts: dict[str, Any]) -> bool:
    if isinstance(condition, list):
        return all(_condition_matches(item, facts) for item in condition)
    actual = facts.get(condition.field)
    return _matches(actual, condition.operator, condition.value)


def _evidence_for(condition: RuleCondition | list[RuleCondition], facts: dict[str, Any]) -> dict[str, Any]:
    if isinstance(condition, list):
        return {"all": [_evidence_for(item, facts) for item in condition]}
    return {
        "field": condition.field,
        "operator": condition.operator,
        "expected": condition.value,
        "actual": facts.get(condition.field),
    }


def _matches(actual: Any, operator: str, expected: Any) -> bool:
    if operator == ">":
        return actual is not None and actual > expected
    if operator == ">=":
        return actual is not None and actual >= expected
    if operator == "<":
        return actual is not None and actual < expected
    if operator == "<=":
        return actual is not None and actual <= expected
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    if operator == "in":
        return actual in expected
    raise ValueError(f"Unsupported rule operator: {operator}")
