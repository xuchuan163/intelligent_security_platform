from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DynamicFactorDefinition:
    factor_code: str
    group: str
    factor_name: str
    field: str
    operator: str
    value: Any
    delta: float
    evidence_source: str | None = None


@dataclass(frozen=True)
class DynamicFactorTrigger:
    factor_code: str
    factor_name: str
    group: str
    delta: float
    evidence_ref: str


@dataclass(frozen=True)
class DynamicFactorConfig:
    version: str
    effective_from: str
    base_factor: float
    max_factor: float
    exclusive_groups: frozenset[str]
    factors: tuple[DynamicFactorDefinition, ...]


@dataclass(frozen=True)
class DynamicFactorEvaluation:
    factor: float
    triggers: tuple[DynamicFactorTrigger, ...]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _matches(actual: Any, operator: str, expected: Any) -> bool:
    if actual is None:
        return False
    if operator == ">":
        return actual > expected
    if operator == ">=":
        return actual >= expected
    if operator == "<":
        return actual < expected
    if operator == "<=":
        return actual <= expected
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    raise ValueError(f"Unsupported operator: {operator}")


def load_dynamic_factor_config(config_path: Path | None = None) -> DynamicFactorConfig:
    path = config_path or _repo_root() / "config" / "weights" / "dynamic_factors.yaml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    factors = tuple(
        DynamicFactorDefinition(
            factor_code=str(item["factor_code"]),
            group=str(item["group"]),
            factor_name=str(item["factor_name"]),
            field=str(item["field"]),
            operator=str(item["operator"]),
            value=item.get("value"),
            delta=float(item["delta"]),
            evidence_source=item.get("evidence_source"),
        )
        for item in payload.get("factors") or []
    )
    return DynamicFactorConfig(
        version=str(payload.get("version", "0.0.0")),
        effective_from=str(payload.get("effective_from", "")),
        base_factor=float(payload.get("base_factor", 1.0)),
        max_factor=float(payload.get("max_factor", 1.5)),
        exclusive_groups=frozenset(payload.get("exclusive_groups") or []),
        factors=factors,
    )


@lru_cache(maxsize=1)
def default_dynamic_factor_config() -> DynamicFactorConfig:
    return load_dynamic_factor_config()


def evaluate_dynamic_factors(
    facts: dict[str, Any],
    *,
    config: DynamicFactorConfig | None = None,
) -> DynamicFactorEvaluation:
    resolved = config or default_dynamic_factor_config()
    triggered: list[DynamicFactorTrigger] = []

    for definition in resolved.factors:
        if not _matches(facts.get(definition.field), definition.operator, definition.value):
            continue
        triggered.append(
            DynamicFactorTrigger(
                factor_code=definition.factor_code,
                factor_name=definition.factor_name,
                group=definition.group,
                delta=definition.delta,
                evidence_ref=definition.evidence_source or definition.field,
            )
        )

    group_deltas: dict[str, float] = {}
    ungrouped_delta = 0.0
    for trigger in triggered:
        if trigger.group in resolved.exclusive_groups:
            group_deltas[trigger.group] = max(group_deltas.get(trigger.group, 0.0), trigger.delta)
        else:
            ungrouped_delta += trigger.delta

    total_delta = ungrouped_delta + sum(group_deltas.values())
    factor = min(resolved.max_factor, resolved.base_factor + total_delta)
    return DynamicFactorEvaluation(factor=round(factor, 4), triggers=tuple(triggered))


def dynamic_factor_evidence(
    evaluation: DynamicFactorEvaluation,
    *,
    config: DynamicFactorConfig | None = None,
) -> list[str]:
    resolved = config or default_dynamic_factor_config()
    evidence = [f"factor:{trigger.factor_code}" for trigger in evaluation.triggers]
    if evaluation.triggers:
        evidence.append(f"factor:version:{resolved.version}")
        evidence.append(f"factor:multiplier:{evaluation.factor}")
    return evidence
