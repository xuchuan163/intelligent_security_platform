"""Expert prior nodes for Bayesian L2 attribution (§18.3 subset)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FactorCategory = Literal["人", "机", "料", "法", "环", "管"]


@dataclass(frozen=True)
class RiskFactor:
    factor_id: str
    category: FactorCategory
    label: str
    prior: float


@dataclass(frozen=True)
class AccidentOutcome:
    outcome_id: str
    label: str
    prior: float


RISK_FACTORS: tuple[RiskFactor, ...] = (
    RiskFactor("human_training_gap", "人", "培训不足", 0.10),
    RiskFactor("human_violation", "人", "违规操作", 0.12),
    RiskFactor("human_fatigue", "人", "疲劳作业", 0.08),
    RiskFactor("human_health_mismatch", "人", "健康不适配", 0.07),
    RiskFactor("human_uncertified", "人", "无证作业", 0.09),
    RiskFactor("machine_fault", "机", "设备故障", 0.08),
    RiskFactor("machine_maintenance_gap", "机", "维保缺失", 0.10),
    RiskFactor("machine_guard_failure", "机", "防护装置失效", 0.07),
    RiskFactor("material_fire_risk", "料", "易燃材料堆放", 0.05),
    RiskFactor("material_stack_unstable", "料", "材料堆码不稳", 0.04),
    RiskFactor("method_plan_missing", "法", "方案缺失", 0.06),
    RiskFactor("method_briefing_gap", "法", "交底不到位", 0.09),
    RiskFactor("method_permit_irregular", "法", "作业票不规范", 0.08),
    RiskFactor("env_weather", "环", "大风高温", 0.05),
    RiskFactor("env_night_lighting", "环", "夜间照明不足", 0.06),
    RiskFactor("env_cross_operation", "环", "交叉作业", 0.10),
    RiskFactor("mgmt_oversight_gap", "管", "监管缺位", 0.10),
    RiskFactor("mgmt_rectification_gap", "管", "整改不闭环", 0.12),
    RiskFactor("mgmt_subcontractor_weak", "管", "分包管理弱", 0.11),
    RiskFactor("mgmt_schedule_pressure", "管", "赶工期", 0.11),
    RiskFactor("mgmt_safety_investment", "管", "安全投入不足", 0.05),
)

ACCIDENT_OUTCOMES: tuple[AccidentOutcome, ...] = (
    AccidentOutcome("fall_from_height", "高处坠落", 0.22),
    AccidentOutcome("electric_shock", "触电", 0.14),
    AccidentOutcome("struck_by_object", "物体打击", 0.16),
    AccidentOutcome("collapse", "坍塌", 0.12),
    AccidentOutcome("fire", "火灾", 0.10),
    AccidentOutcome("mechanical_injury", "机械伤害", 0.18),
    AccidentOutcome("other", "其他", 0.08),
)

# Expert likelihood P(outcome | factor); sparse subset aligned with §18.3 result nodes.
OUTCOME_LIKELIHOOD: dict[str, dict[str, float]] = {
    "human_training_gap": {
        "fall_from_height": 0.28,
        "electric_shock": 0.10,
        "struck_by_object": 0.14,
        "collapse": 0.08,
        "fire": 0.05,
        "mechanical_injury": 0.12,
    },
    "human_violation": {
        "fall_from_height": 0.20,
        "electric_shock": 0.18,
        "struck_by_object": 0.16,
        "collapse": 0.06,
        "fire": 0.12,
        "mechanical_injury": 0.20,
    },
    "human_uncertified": {
        "fall_from_height": 0.16,
        "electric_shock": 0.30,
        "struck_by_object": 0.10,
        "collapse": 0.05,
        "fire": 0.08,
        "mechanical_injury": 0.18,
    },
    "human_health_mismatch": {
        "fall_from_height": 0.22,
        "electric_shock": 0.08,
        "struck_by_object": 0.10,
        "collapse": 0.06,
        "fire": 0.04,
        "mechanical_injury": 0.10,
    },
    "machine_fault": {
        "fall_from_height": 0.08,
        "electric_shock": 0.22,
        "struck_by_object": 0.12,
        "collapse": 0.10,
        "fire": 0.08,
        "mechanical_injury": 0.30,
    },
    "machine_maintenance_gap": {
        "fall_from_height": 0.10,
        "electric_shock": 0.18,
        "struck_by_object": 0.10,
        "collapse": 0.12,
        "fire": 0.10,
        "mechanical_injury": 0.28,
    },
    "machine_guard_failure": {
        "fall_from_height": 0.32,
        "electric_shock": 0.06,
        "struck_by_object": 0.22,
        "collapse": 0.08,
        "fire": 0.04,
        "mechanical_injury": 0.20,
    },
    "material_fire_risk": {
        "fall_from_height": 0.02,
        "electric_shock": 0.06,
        "struck_by_object": 0.04,
        "collapse": 0.04,
        "fire": 0.70,
        "mechanical_injury": 0.04,
    },
    "method_plan_missing": {
        "fall_from_height": 0.14,
        "electric_shock": 0.10,
        "struck_by_object": 0.08,
        "collapse": 0.28,
        "fire": 0.06,
        "mechanical_injury": 0.10,
    },
    "method_briefing_gap": {
        "fall_from_height": 0.24,
        "electric_shock": 0.14,
        "struck_by_object": 0.14,
        "collapse": 0.10,
        "fire": 0.08,
        "mechanical_injury": 0.12,
    },
    "method_permit_irregular": {
        "fall_from_height": 0.16,
        "electric_shock": 0.26,
        "struck_by_object": 0.10,
        "collapse": 0.08,
        "fire": 0.14,
        "mechanical_injury": 0.14,
    },
    "env_cross_operation": {
        "fall_from_height": 0.18,
        "electric_shock": 0.12,
        "struck_by_object": 0.24,
        "collapse": 0.10,
        "fire": 0.08,
        "mechanical_injury": 0.16,
    },
    "env_night_lighting": {
        "fall_from_height": 0.30,
        "electric_shock": 0.10,
        "struck_by_object": 0.18,
        "collapse": 0.06,
        "fire": 0.06,
        "mechanical_injury": 0.10,
    },
    "mgmt_rectification_gap": {
        "fall_from_height": 0.20,
        "electric_shock": 0.12,
        "struck_by_object": 0.12,
        "collapse": 0.18,
        "fire": 0.10,
        "mechanical_injury": 0.12,
    },
    "mgmt_oversight_gap": {
        "fall_from_height": 0.18,
        "electric_shock": 0.14,
        "struck_by_object": 0.14,
        "collapse": 0.14,
        "fire": 0.10,
        "mechanical_injury": 0.14,
    },
    "mgmt_subcontractor_weak": {
        "fall_from_height": 0.16,
        "electric_shock": 0.10,
        "struck_by_object": 0.14,
        "collapse": 0.12,
        "fire": 0.08,
        "mechanical_injury": 0.16,
    },
    "mgmt_schedule_pressure": {
        "fall_from_height": 0.22,
        "electric_shock": 0.10,
        "struck_by_object": 0.16,
        "collapse": 0.14,
        "fire": 0.08,
        "mechanical_injury": 0.14,
    },
}

FACTOR_BY_ID: dict[str, RiskFactor] = {item.factor_id: item for item in RISK_FACTORS}
OUTCOME_BY_ID: dict[str, AccidentOutcome] = {item.outcome_id: item for item in ACCIDENT_OUTCOMES}

# Map Chinese accident labels from case library to outcome ids.
ACCIDENT_TYPE_ALIASES: dict[str, str] = {
    "高处坠落": "fall_from_height",
    "高处落物": "struck_by_object",
    "物体打击": "struck_by_object",
    "触电": "electric_shock",
    "坍塌": "collapse",
    "模板支撑失稳": "collapse",
    "脚手架倒塌": "collapse",
    "火灾": "fire",
    "机械伤害": "mechanical_injury",
    "起重伤害": "mechanical_injury",
    "塔吊倾覆": "mechanical_injury",
    "车辆伤害": "mechanical_injury",
    "中毒窒息": "other",
    "灼烫": "other",
    "淹溺": "other",
    "地下管线破损": "other",
    "冬季施工滑坠": "fall_from_height",
    "夜间施工": "fall_from_height",
    "分包管理失控": "other",
    "文明施工": "other",
}

MODEL_VERSION = "bayesian-l2-v1"
MODEL_LEVEL = "L2"
