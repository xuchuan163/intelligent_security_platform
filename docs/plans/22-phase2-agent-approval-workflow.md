# Phase 2 / 2.4-F-A Agent Approval Workflow

> 本设计只覆盖 2.4-F-A：Agent 写操作进入人工确认队列。它不允许 Agent 自动创建、派发、流转、关闭工单，也不执行处罚、停工、清退。

## 1. 背景

2.4-D 已实现受控 DAG 执行器，`controlled_execute` 只执行只读工具，写工具返回 `approval_required`，受限工具返回 `blocked`。2.4-E 已扩展更多只读工具，但写侧仍停留在内存态结果，缺少可审计、可查询、可人工处理的确认队列。

2.4-F-A 的目标是把写侧 `approval_required` 固化为数据库确认单，并提供最小 API 给前端或人工审核页读取、批准、驳回。批准只代表人工确认，不触发真实业务写入。

## 2. 设计原则

- Agent 不直接执行业务写操作。
- 写工具只生成 `agent_approval_request`。
- `approve` / `reject` 只修改确认单状态，不调用工单、隐患、处罚、停工等业务 service。
- 受限工具不进入确认队列，继续直接 `blocked`。
- 队列记录必须带 `company_id`、`project_id`、`scope_type`、`request_user_id`，并受 `apply_data_scope` 过滤。
- 队列 payload 只保存结构化、白名单化的建议参数，不保存任意 LLM 原文作为可执行载荷。

## 3. 工具边界

可进入人工确认队列：

| Tool | 说明 |
|---|---|
| `work_orders.create` | 建议创建工单 |
| `work_orders.dispatch` | 建议派发工单 |
| `work_orders.transition` | 建议流转工单状态 |
| `hazards.create` | 建议创建隐患 |

继续直接阻断：

| Tool | 原因 |
|---|---|
| `penalty.create` | 处罚必须走独立人工责任链 |
| `stop_work.issue` | 停工属于高风险处置 |
| `subcontractor.remove` | 清退属于高风险处置 |

## 4. 数据模型

新增表：`agent_approval_request`

核心字段：

| 字段 | 说明 |
|---|---|
| `approval_id` | 业务唯一 ID，格式 `AGAPR-*` |
| `run_id` | DAG run ID |
| `step_run_id` | DAG step run ID |
| `tenant_id` | 兼容旧租户字段 |
| `company_id` | 公司级租户边界 |
| `project_id` | 项目数据边界，可为空 |
| `scope_type` | `company` / `project` |
| `request_user_id` | 发起 Agent 请求的用户 |
| `requested_tool` | 写工具名称 |
| `requested_action` | DAG step action |
| `target_type` | `work_order` / `hazard` / `unknown` |
| `target_id` | 目标业务 ID，可为空 |
| `payload_summary` | 人审摘要 |
| `payload_json` | 结构化建议参数 |
| `risk_level` | `low` / `medium` / `high` |
| `reason` | 进入人审的原因 |
| `evidence_refs` | 证据引用 |
| `status` | `pending` / `approved` / `rejected` / `expired` / `cancelled` |
| `approver_user_id` | 审批人 |
| `approval_comment` | 审批意见 |
| `created_at` / `updated_at` / `approved_at` / `rejected_at` / `expires_at` | 审计时间 |

## 5. DAG 行为

`controlled_execute` 遇到写工具时：

1. 保持 `will_execute=false`。
2. 生成 `step_run_id`。
3. 创建一条 `agent_approval_request(status=pending)`。
4. step result 返回：

```json
{
  "status": "approval_required",
  "will_execute": false,
  "approval_id": "AGAPR-...",
  "output_summary": {
    "approval_id": "AGAPR-...",
    "requested_tool": "work_orders.transition",
    "approval_status": "pending"
  }
}
```

5. DAG run status 保持 `approval_required`。

`dry_run` 不创建确认单。

## 6. API

新增 API：

```http
GET  /api/v1/agent/approvals
GET  /api/v1/agent/approvals/{approval_id}
POST /api/v1/agent/approvals/{approval_id}/approve
POST /api/v1/agent/approvals/{approval_id}/reject
```

API 行为：

- 列表和详情必须按当前用户 `company_id/project_id` 过滤。
- `approve` 只把 `status` 改为 `approved`，记录审批人和意见。
- `reject` 只把 `status` 改为 `rejected`，记录审批人和意见。
- 非 `pending` 状态不可重复审批。
- 本阶段不提供 `execute` API。

## 7. 测试范围

新增测试：

- ORM metadata 包含 `agent_approval_request`。
- `controlled_execute` 遇到 `work_orders.transition` 会创建 pending approval。
- 写工具不会修改 `safety_work_order.status`。
- `dry_run` 不创建 approval。
- restricted tool 不创建 approval。
- 越权 project 不创建 approval。
- approval 列表按 company/project scope 过滤。
- approve/reject 只改确认单状态，不执行业务 service。
- `/agent/ask` controlled_execute 返回 `approval_id`。

## 8. 非目标

- 不实现真实业务执行。
- 不开放 Agent 自动创建、派发、关闭工单。
- 不让处罚、停工、清退进入普通确认队列。
- 不引入新中间件。
- 不改现有工单 workflow service 的状态机。

## 9. 验收

- Alembic 可升级到 head。
- `python scripts/check_db_schema.py` 通过。
- Agent approval 相关 pytest 通过。
- 全量 `pytest -q` 通过。
- `controlled_execute` 写工具返回 `approval_required + approval_id`。

## 10. 实现记录（2026-06-07）

- 已新增 ORM 模型 `AgentApprovalRequest`。
- 已新增迁移 `backend/alembic/versions/20260607_0011_agent_approval_request.py`。
- 已新增 service：`backend/app/services/agents/approval_queue.py`。
- 已新增 API：`GET /api/v1/agent/approvals`、`GET /api/v1/agent/approvals/{approval_id}`、`POST /approve`、`POST /reject`。
- 已接入 DAG executor：`controlled_execute` 写工具步骤会创建 pending approval，并返回 `approval_id`。
- 已扩展 planner：明确的工单流转请求可生成 `work_orders.transition` 人审步骤。
- 已验证 approve/reject 只修改确认单状态，不触发工单流转。
- 已验证 restricted tools 不进入确认队列。
