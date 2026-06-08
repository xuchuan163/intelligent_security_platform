# Phase 2 / 2.4-G Human-Approved Work-Order Execution

> 本设计只覆盖 2.4-G：人工批准后的确认单，由人工点击执行 `work_orders.transition`。Agent 不自动执行任何业务写操作。

## 1. 目标

在 2.4-F-A 的 `agent_approval_request` 基础上，增加一个人工执行入口。执行入口只允许处理已经 `approved` 的 `work_orders.transition` 确认单，并在执行前重新使用当前点击人的身份调用现有工单 workflow service。

## 2. 边界

本阶段只做：

- `requested_tool = work_orders.transition`
- `status = approved`
- 人工点击 `POST /api/v1/agent/approvals/{approval_id}/execute`
- 从 `payload_json` 还原 `WorkOrderStatusUpdate`
- 调用 `transition_work_order(db, work_order_id, payload, current_user)`
- 将执行结果回写 `agent_approval_request`

本阶段不做：

- Agent 自动执行
- `hazards.create`
- `work_orders.create`
- 独立 `work_orders.dispatch`
- 处罚、停工、清退
- 执行附件上传
- 绕过现有工单状态机或岗位矩阵

## 3. 状态机

确认单状态扩展为：

```text
pending
approved
rejected
executed
execution_failed
expired
cancelled
```

允许转换：

```text
approved -> executed
approved -> execution_failed
```

禁止转换：

```text
pending -> executed
rejected -> executed
executed -> executed
execution_failed -> executed
```

失败是否允许重新执行，留到后续评审。本阶段不允许自动重试。

## 4. 数据模型补充

在 `agent_approval_request` 增加：

| 字段 | 说明 |
|---|---|
| `executor_user_id` | 点击执行的人工用户 |
| `executed_at` | 执行成功时间 |
| `execution_result` | 业务 service 返回摘要 |
| `execution_error` | 执行失败原因 |

审批人和执行人分开记录：

- `approver_user_id`：批准该确认单的人
- `executor_user_id`：真正点击执行业务动作的人

## 5. 执行规则

执行入口必须：

1. 按当前用户 `company_id/project_id` 查询确认单。
2. 要求 `status = approved`。
3. 要求 `requested_tool = work_orders.transition`。
4. 要求 `target_type = work_order`。
5. 从 `payload_json.work_order_id` 或 `target_id` 取得工单 ID。
6. 从 `payload_json` 构造 `WorkOrderStatusUpdate`。
7. 使用当前用户调用 `transition_work_order()`。

`transition_work_order()` 会再次校验：

- data_scope
- 项目访问权限
- 项目角色
- 工单当前状态
- 岗位动作矩阵
- 必填字段

因此即使确认单已经 approved，执行时仍可能失败。

## 6. API

新增：

```http
POST /api/v1/agent/approvals/{approval_id}/execute
```

返回：

```json
{
  "approval_id": "AGAPR-...",
  "status": "executed",
  "executor_user_id": "U-DIR-01",
  "execution_result": {
    "work_order_id": "WO-001",
    "action": "confirm",
    "new_status": "dispatched"
  }
}
```

错误映射：

- 确认单不存在或越权：404
- 状态不是 `approved`：409
- 工具不允许执行：403
- 工单 workflow 权限失败：403
- payload 缺字段或状态机冲突：409/422

## 7. 测试范围

- `approved + safety_director + confirm` 可执行成功，工单变为 `dispatched`。
- `pending` 不可执行。
- `rejected` 不可执行。
- `executed` 不可重复执行。
- 项目越权用户不可执行。
- 角色不匹配用户不可执行，并回写 `execution_failed`。
- 非 `work_orders.transition` 不可执行。
- API `POST /execute` 返回统一成功响应。
- Agent `controlled_execute` 仍只生成 approval，不会自动执行。

## 8. 验收

- Alembic 可升级到 head。
- `python scripts/check_db_schema.py` 通过。
- 目标测试通过。
- 全量后端 pytest 通过。
- 工单 workflow service 仍是唯一业务执行入口。

## 9. 实现记录（2026-06-07）

- 已新增迁移 `backend/alembic/versions/20260607_0012_agent_approval_execution.py`。
- 已为 `agent_approval_request` 增加 `executor_user_id`、`executed_at`、`execution_result`、`execution_error`。
- 已新增 `execute_approved_request()`，只执行 `work_orders.transition`。
- 已新增 `POST /api/v1/agent/approvals/{approval_id}/execute`。
- 已验证执行成功会调用 `transition_work_order()` 并回写 `executed`。
- 已验证 pending/rejected/executed/execution_failed 不可执行。
- 已验证角色不匹配会走 workflow 权限校验并回写 `execution_failed`。
- 已验证 Agent `controlled_execute` 仍然只生成 pending approval，不自动执行工单。
