# 02 Rule Engine Plan

## Goal

把已配置的强规则从“只写触发日志”推进到“触发日志 + 工单建议/自动工单”，形成可演示的安全闭环。

## Scope

- 读取 `config/rules/*.yaml` 的 `action` 工单字段；
- 画像重算时根据规则触发结果生成工单；
- 按 `rule_id + object_type + object_id + project_id + 未闭环状态` 去重；
- 返回 `created_work_orders` 和 `skipped_duplicate_work_orders`；
- 保持单体 FastAPI，不引入队列或外部系统。

## Out Of Scope

- 不接企业微信/OA；
- 不做异步调度；
- 不做复杂规则 DSL；
- 不自动关闭或处罚；
- 不做附件上传。

## Work Order Trigger Contract

规则 `action` 支持字段：

```yaml
action:
  risk_bonus: 20
  suggested_work_order_type: hazard_rectification
  work_order_title_template: 重大隐患超期未闭环整改
  work_order_priority: urgent
  auto_create_work_order: true
```

去重范围：

- `rule_id`
- `source_type`
- `source_id`
- `project_id`
- `status != closed`

## Acceptance

- 项目强规则触发后自动生成工单；
- 工人强规则触发后自动生成工单；
- 重复重算不会重复生成未闭环工单；
- `POST /profile/recalculate` 返回创建和跳过去重数量；
- `pytest backend/tests -q` 通过。
