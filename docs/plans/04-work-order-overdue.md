# 04 Work Order Overdue Escalation Plan

## Goal

`processing` 状态工单超期后可通过 API 转为 `overdue_escalated`（Task 1.4.5）。

## Scope

- 新增 service 调用：`services/work_orders/service.py::escalate_overdue_work_orders`
- 新增 `POST /api/v1/work-orders/escalate-overdue`（MVP 用手动/API 触发，不做 Celery）
- 配置：`PROCESSING_TIMEOUT_HOURS`（默认 72）写入 `core/config.py`
- 测试：`tests/services/test_work_order_escalation.py`（domain `timeout` 转换 + API）

## Out Of Scope

- 定时 Cron / Airflow
- 三级升级链、OA 回写

## Steps

1. [x] 测试：processing 且超期 → `timeout` action → `overdue_escalated`
2. [x] 实现批量扫描 + 状态机 `timeout` 流转
3. [x] endpoint 薄封装 + smoke
4. [x] Dashboard 展示 `overdue_work_orders` 已有字段验证（字段已按状态统计）
5. [x] 勾选 1.4.5

## Acceptance

种子中构造 1 条超时 processing 工单，调用 escalate API 后 status 为 `overdue_escalated`。

## Result

- 新增 `POST /api/v1/work-orders/escalate-overdue`；
- 默认 `processing_timeout_hours=72`，从 `.env` 可覆盖；
- 扫描当前 data_scope 内 `processing` 工单，`due_time` 已过期或无 `due_time` 且 `updated_at` 超过阈值时升级；
- 升级后写入 `escalation_level` 和 `escalation_history.events`；
- 暂不引入 Cron，后续定时任务复用同一 service 函数。
