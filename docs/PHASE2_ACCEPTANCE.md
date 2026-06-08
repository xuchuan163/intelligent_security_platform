# Phase 2 里程碑验收报告

**验收日期：** 2026-06-03  
**验收范围：** `docs/IMPLEMENTATION_ROADMAP.md` §209–215 五项门禁  
**验证环境：** Python 3.12.10，`backend/` 目录，`pytest` 门禁子集

---

## 1. 总览

| 里程碑 | 目标 | 结论 | 证据摘要 |
|---|---|---|---|
| 问数准确率 | ≥ 85% | **通过** | 105 用例全通过；`audit_pass_rate=1.0`；`generation_valid_rate=0.8667` |
| 6 Agent 可演示编排 | 六路路由 + DAG 可演示 | **通过** | 路由 6/6、DAG dry/controlled、审批队列、前端 3 页 |
| 会话多轮上下文命中率 | ≥ 90% | **通过** | 85 用例基准集，`context_hit_rate=1.0` |
| Prompt 版本登记/回滚 | 可登记且可回滚 | **通过** | `GET/POST /agent/prompts*` + hash 变更自动版本递增 |
| 权限越权拦截率 | 100% | **通过** | data_scope + company/project scope 测试 11+ 条全绿 |

**Phase 2 里程碑结论：通过** — 五项门禁均已达标（含 Prompt 回滚 API 与 Agent/NL2SQL 记忆接入）。

---

## 2. 自动化验证

### 2.1 执行命令

```bash
cd backend
py -3.12 -m pytest \
  tests/services/test_nl2sql_benchmark.py \
  tests/services/test_nl2sql_clarification.py \
  tests/services/test_nl2sql_auditor.py \
  tests/services/test_nl2sql_generator.py \
  tests/api/test_nl2sql_api_gate.py \
  tests/services/test_agent_router.py \
  tests/services/test_agent_prompt_versions.py \
  tests/services/test_agent_dag_executor.py \
  tests/services/test_agent_feedback.py \
  tests/api/test_agent_feedback_api.py \
  tests/api/test_agent_ask_api.py \
  tests/services/test_hazard_rectification_advisor.py \
  tests/services/test_memory_service.py \
  tests/test_memory_api.py \
  tests/services/test_company_project_scope.py \
  tests/services/test_data_scope.py \
  tests/test_auth_mock.py \
  -q
```

**结果：** `85 passed`（2026-06-03）

### 2.2 NL2SQL Benchmark 指标

数据集：`backend/tests/datasets/nl2sql_100.jsonl`（105 条）

| 指标 | 实测值 | 门禁 |
|---|---:|---:|
| `passed_cases / total_cases` | 105 / 105 | 100% |
| `audit_pass_rate`（合法 SQL 审计通过率） | 1.0 | ≥ 0.85（里程碑）/ ≥ 0.95（测试阈值） |
| `generation_valid_rate` | 0.8667 | ≥ 0.80（测试阈值） |
| `unsafe_block_rate` | 1.0 | 100% 拦截 |
| `clarification_rate` | 1.0 | 歧义用例全部返回澄清 |

---

## 3. 分项验收

### 3.1 问数准确率 ≥ 85%

- **实现：** SQL 白名单 + AST 审计、Mock/Qwen 候选生成、`POST /api/v1/agent/nl2sql` API 门禁、多轮澄清（2.3.5）
- **前端：** `/agent/nl2sql` 多轮对话页
- **结论：** 通过。静态基准 105/105；合法查询审计通过率 100%。

### 3.2 6 Agent 可演示编排

| Agent | 路由关键词示例 | 验证 |
|---|---|---|
| `safety_supervisor` | 安全问题交给谁 | `test_agent_router` |
| `risk_profile_analyst` | 项目画像风险解释 | 同上 |
| `rule_compliance_checker` | SR-PROJ-001 证据 | 同上 |
| `work_order_coordinator` | 工单超期闭环 | 同上 |
| `nl2sql_analyst` | 项目风险排名 | 同上 + API gate |
| `hazard_rectification_advisor` | 隐患整改建议 | 同上 + hazard advisor |

- **DAG 模式：** `route_only` / `execute_preview` / `plan_only` / `dry_run` / `controlled_execute`
- **写操作：** `work_orders.create` / `work_orders.transition` 走审批队列
- **前端演示页：** `/agent/approvals`、`/agent/hazard-advisor`、`/agent/nl2sql`
- **结论：** 通过。

### 3.3 会话多轮上下文命中率 ≥ 90%

**实现：**

- L1 Redis 会话 + 跨轮 `context`/`summary` 合并（`merge_session_context`）
- 上下文解析：`resolve_follow_up_context` + 实体抽取（P00x/H00x/WO/SR/M- 等）
- 基准集：`tests/datasets/memory_context_55.jsonl`（**85 条**，9 类场景）
- 跑分器：`app/services/memory/benchmark.py` → `context_hit_rate`
- 测试：`tests/services/test_memory_context_benchmark.py`

**实测（2026-06-03）：**

| 指标 | 值 |
|---|---:|
| `total_cases` | 85 |
| `passed_cases` | 85 |
| `context_hit_rate` | 1.0 |

**类别覆盖：** `project_reference`、`hazard_reference`、`work_order_reference`、`metric_reference`、`rule_reference`、`multi_entity`、`pronoun_follow_up`、`nl2sql_clarification`、`context_sanitization`

**结论：** 通过（≥ 90% 门禁）。

### 3.4 Prompt 版本可登记/回滚

**已实现：**

- `prompts/agents/` 六份 System Prompt
- `agent_prompt_version` 表 + `sync_agent_prompt_versions()` hash 登记
- 路由/DAG 返回 `prompt_version` + `prompt_hash`
- 测试：`test_agent_prompt_versions.py`（6 Prompt 同步）

**已实现（Phase 2 收尾）：**

- `GET /api/v1/agent/prompts` — 列出版本（含 archived）
- `POST /api/v1/agent/prompts/sync` — 从 `prompts/agents/` 同步；hash 变更时自动递增 `v1.N`
- `POST /api/v1/agent/prompts/{agent_code}/activate` — 回滚/切换激活版本

**结论：** 通过。

### 3.5 权限越权拦截率 100%

| 测试文件 | 用例数 | 覆盖点 |
|---|---:|---|
| `test_data_scope.py` | 9 | 工单/画像/dashboard/规则 org_scope |
| `test_company_project_scope.py` | 4 | company vs project 视图、越权 project |
| `test_auth_mock.py` | 1+ | `/auth/me` mock 用户 |
| `test_agent_dag_executor.py` | 含 | 未授权 project 阻断 DAG |
| `test_nl2sql_auditor.py` | 含 | tenant/project scope 注入与覆盖拒绝 |

**结论：** 通过。越权场景在 service/audit/DAG 层均有拒绝路径且测试全绿。

---

## 4. 演示清单（curl）

> 默认租户/用户见 `seed_demo_data.py`；本地端口以 `main.py` 为准（常见 8011）。

### 4.1 六 Agent 路由

```bash
curl -s -X POST http://127.0.0.1:8011/api/v1/agent/ask \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC-DEMO" \
  -H "X-Mock-User-Id: U-DIR-01" \
  -d '{"message":"查询项目风险排名前十","execution_mode":"route_only"}'
```

### 4.2 NL2SQL（审计 + 可选执行）

```bash
curl -s -X POST http://127.0.0.1:8011/api/v1/agent/nl2sql \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC-DEMO" \
  -H "X-Mock-User-Id: U-DIR-01" \
  -d '{"question":"列出高风险项目","provider":"local_mock","execute":false}'
```

### 4.3 隐患整改 DAG（controlled_execute + 审批）

```bash
curl -s -X POST http://127.0.0.1:8011/api/v1/agent/ask \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC-DEMO" \
  -H "X-Mock-User-Id: U-PM-P001" \
  -H "X-Scope-Type: project" \
  -H "X-Project-Id: P001" \
  -d '{
    "message":"请为这个隐患生成整改工单",
    "execution_mode":"controlled_execute",
    "context":{"hazard_id":"H002","project_id":"P001","propose_work_order":true}
  }'
```

### 4.4 会话记忆

```bash
curl -s -X POST http://127.0.0.1:8011/api/v1/memory/session \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC-DEMO" \
  -H "X-Mock-User-Id: U-DIR-01" \
  -d '{"session_id":"DEMO-S001","messages":[{"role":"user","content":"上次问了哪些高风险项目？"}]}'
```

### 4.5 Agent 反馈

```bash
curl -s -X POST http://127.0.0.1:8011/api/v1/agent/feedback \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC-DEMO" \
  -H "X-Company-Id: CSCEC-DEMO" \
  -H "X-Mock-User-Id: U-DIR-01" \
  -d '{"task_id":"DEMO-TASK","agent_name":"nl2sql_analyst","feedback_type":"thumb","rating":1}'
```

---

## 5. 遗留与建议

| 项 | 优先级 | 说明 |
|---|---|---|
| Docker Compose Redis 生产化调优 | P3 | 已加入 `deploy/docker-compose.yml`；可按需开启持久化 |
| 2.2.4 指标扩展至 100 | P3 | 种子已 100 条；与 Phase 1 的 32 条演示指标并存，需文档对齐 |

---

## 6. 签核

| 角色 | 签字 | 日期 |
|---|---|---|
| 开发 | AI Agent 自动验收 | 2026-06-03 |
| 产品/业务 | （待填） | |
| 技术负责人 | （待填） | |
