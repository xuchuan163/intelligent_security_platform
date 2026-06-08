# 02 Rule Engine Expand Plan

## Goal

强规则已从 **6 条** 扩展到 **10 条**（附录 B 核心 subset），全部 YAML 驱动、测试覆盖。

## Scope（Task 1.1.6）

- 在 `config/rules/project_rules.yaml` 新增 `SR-PROJ-003`
- 新增 `config/rules/subcontractor_rules.yaml`，包含 `SR-SUB-001/002/004`
- 扩展 `test_rule_engine.py`：加载数量 ≥ 10，并覆盖分包商规则触发

## Out Of Scope

- 独立 rule-engine 微服务
- 30+ 全量附录 B（Phase 2+）
- Webhook 推送

## Files

- `config/rules/*.yaml`
- `backend/tests/services/test_rule_engine.py`
- `backend/app/services/profiles/calculator.py`
- `backend/app/services/profiles/service.py`

## Steps

1. [x] 对照技术文档附录 B 选定 4 条，写 YAML + 单元测试 fixture 数据
2. [x] `test_rule_engine_loads_at_least_10_rules`
3. [x] 画像重算 smoke：新规则可写 `rule_trigger_log`
4. [x] 勾选 1.1.6

## Acceptance

`pytest -v tests/services/test_rule_engine.py` 全绿；`RuleEngine.from_config()` 规则数 ≥ 10。

## Result

- 当前强规则数：10 条；
- 新增项目规则：`SR-PROJ-003` 高工期压力项目；
- 新增分包商规则：`SR-SUB-004` 重大隐患超期未整改、`SR-SUB-001` 安全生产许可证异常、`SR-SUB-002` 存在历史事故；
- 分包商画像已接入 `RuleEngine`，重算时写入 `rule_trigger_log`；
- `SR-SUB-001`、`SR-SUB-004` 自动创建去重工单，`SR-SUB-002` 只计分与写日志。
