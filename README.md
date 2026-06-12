# 中建智慧安全平台

面向中建集团项目工地安全管理的全栈平台：FastAPI 后端、Vue3 前端、MySQL 主库、三类风险画像、强规则预警、工单闭环、四库协同、Agent 智能能力与 Phase 4 算法增强。

> **项目状态（2026-06-08）：已收口。** Phase 0–4 完成，业务闭环成立；延后扩展不再实施。详见 [`docs/PROJECT_CLOSURE.md`](docs/PROJECT_CLOSURE.md)。

## Phase 1 状态

Phase 1 MVP 收尾已完成，可进入总体验收和 Phase 2 启动评审。已覆盖：

- 三类画像查询、排名、重算，返回 `calculated_at` 与 `confidence_level`
- 10 条强规则 YAML，可写入触发日志并去重自动建单
- 工单创建、状态流转、前端闭环、超期升级 API
- 指标目录 32 条种子指标与查询 API
- mock 用户、`data_scope` 读路径过滤与 10 条权限测试
- 事故案例库 5 条结构化种子案例与 `GET /api/v1/case/list`
- Qwen 安全助手，无 Key 时降级可用

## Phase 2 启动状态

Phase 2 Sprint 1 已批准只做记忆系统 2.1.x：

- Redis 使用本地 `localhost:6379`，推荐通过 Redis Insight 连接观察。
- 会话热状态写入 `session:{user_id}:{session_id}`，TTL 为 1800 秒。
- MySQL 只归档 `agent_session_summary` 摘要，不保存完整 SQL 结果。
- Checkpoint 热状态写入 Redis，冷状态归档 `agent_task_checkpoint`。
- 暂不实现 NL2SQL、6 Agent DAG、Neo4j。
- Phase 3-C.1 已增加 Milvus standalone（etcd + minio）至 `deploy/docker-compose.yml`。

Phase 2 Sprint 2 指标语义层 2.2.x 已进入轻量增强：

- `POST /api/v1/metrics/validate` 校验指标元数据契约。
- `GET /api/v1/metrics/lineage/{metric_code}` 查询指标血缘。
- `GET /api/v1/metrics/aliases` 查询指标别名映射。
- `metric_catalog` 扩展 `aliases` 字段，种子指标扩展到 100 条。
- 仍不生成 SQL，不开放 NL2SQL。

Phase 2 Sprint 3 NL2SQL 2.3-A 已先做安全底座：

- 新增 `agent_nl2sql_audit` 审计表。
- 新增 SQL AST 审计 service，基于 `sqlglot`。
- 只允许单条 `SELECT`，拒绝写操作、多语句、`SELECT *`、非白名单表和敏感字段。
- 强制注入 `tenant_id`，org scope 用户额外注入 `org_path LIKE ...`。
- 自动补默认 `LIMIT 100`，最大限制 `LIMIT 500`。
- 新增 30 条 `nl2sql_audit_cases.jsonl` 安全审计测试集。
- 仍不开放 `/api/v1/agent/nl2sql`，不接 LLM，不执行 SQL。

Phase 2 Sprint 4 NL2SQL 2.3-B 已增加内部只读执行器：

- 仅执行 SQL 审计器返回的 `sanitized_sql`，不执行原始候选 SQL。
- 审计失败时不执行 SQL，并回写 `execution_status=rejected`。
- 执行成功回写 `execution_status=executed`、`result_row_count`、`result_field_count`。
- 执行异常回写 `execution_status=failed` 和 `execution_error`。
- 返回结果最多 100 行、30 字段，长文本最多 500 字符。
- 仍不开放 `/api/v1/agent/nl2sql`，不接 LLM。

## 安全提醒

`.env` 不提交。阿里云 Key 和数据库密码从环境变量读取。禁止提交身份证号、体检明细、人脸原图、原始视频或真实密钥。

## 本地启动

### PyCharm（推荐）

在 PyCharm 中打开项目根目录，运行配置选择 **PyCharm Start Full Stack**，或直接右键运行根目录 `main.py`。

会自动执行数据库迁移、演示数据初始化，并同时启动：

- 后端 API / Swagger: http://127.0.0.1:8011/docs
- 前端页面: http://127.0.0.1:5173/work-orders

详细说明见 [`docs/PYCHARM_RUN.md`](docs/PYCHARM_RUN.md)。

### 命令行（手动分步）
```bash
docker compose -f deploy/docker-compose.yml up -d
python deploy/scripts/check_stack_health.py

# 或一键启动前后端（等价于 PyCharm main.py）
python main.py

cd backend
pip install -e .
alembic upgrade head
python scripts/seed_demo_data.py
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

cd ../frontend
npm install
npm run dev
```

- 后端 API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- 前端: http://127.0.0.1:5173

## 验证命令

```bash
cd backend
pytest -v
python scripts/check_db_schema.py
..\.venv\Scripts\python.exe scripts\verify_hazard_workflow_demo.py

cd ../frontend
npm run build
```

`verify_hazard_workflow_demo.py` 会通过 API 跑通「隐患上传 -> 安全总监派发 -> 分包接单 -> 提交整改图 -> 总包验收」链路，并校验工单关闭、隐患关闭、流转日志不少于 5 条。

## 常用接口

```bash
curl http://127.0.0.1:8000/api/v1/health
curl "http://127.0.0.1:8000/api/v1/metrics/catalog?page_size=50"
curl "http://127.0.0.1:8000/api/v1/case/list?page_size=10" -H "X-Tenant-Id: CSCEC"
curl -X POST "http://127.0.0.1:8000/api/v1/memory/session" -H "Content-Type: application/json" -H "X-Mock-User-Id: demo-user" -H "X-Tenant-Id: CSCEC" -H "X-Org-Path: CSCEC" -d "{\"session_id\":\"S-DEMO-001\",\"message\":{\"role\":\"user\",\"content\":\"这个项目有什么风险?\"},\"context\":{\"project_id\":\"P001\"},\"summary\":\"用户询问项目风险\"}"
curl "http://127.0.0.1:8000/api/v1/memory/session?session_id=S-DEMO-001" -H "X-Mock-User-Id: demo-user" -H "X-Tenant-Id: CSCEC" -H "X-Org-Path: CSCEC"
curl -X POST "http://127.0.0.1:8000/api/v1/metrics/validate" -H "Content-Type: application/json" -d "{\"metric_codes\":[\"PROJECT_RISK_SCORE\"]}"
curl "http://127.0.0.1:8000/api/v1/metrics/lineage/PROJECT_RISK_SCORE"
curl "http://127.0.0.1:8000/api/v1/metrics/aliases?keyword=Project"
```

## Phase 2 NL2SQL 2.3-C 状态

- 已增加 schema context builder、prompt builder、mock candidate provider 和 Qwen candidate provider。
- `NL2SQL_PROVIDER=mock|qwen|disabled`，默认建议 `disabled`。
- `QWEN_NL2SQL_TIMEOUT_SECONDS` 默认 10 秒。
- Qwen API Key 缺失、超时、异常统一降级为 `generation_failed`。
- Qwen 输出仍必须经过 `audit_sql`，2.3-C 不执行 SQL。

## Phase 2 NL2SQL 2.3-E API Gate

`POST /api/v1/agent/nl2sql` 已开放安全闸门，但默认 `execute=false` 只返回审计结果；需要显式 `execute=true` 才会走只读执行器，且执行前会再次审计。所有请求都会写入 `agent_nl2sql_audit`。

本地 mock 演示：

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/nl2sql" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC" \
  -H "X-Company-Id: CSCEC" \
  -H "X-Mock-User-Id: demo-user" \
  -H "X-Scope-Type: company" \
  -d "{\"question\":\"查询项目列表\",\"provider\":\"mock\",\"mock_llm_output\":\"SELECT project_id, project_name FROM project\"}"
```

执行查询需显式加 `"execute": true`。`provider=mock` 仅允许 `local/test/development` 环境，生产类环境会返回 403。

## Phase 2 Agent 2.4-A Skeleton

`POST /api/v1/agent/ask` 已开放主控路由预览：返回意图、目标 Agent、active prompt version 和 `execution_mode=route_only`。该接口不执行多 Agent DAG、不调用 NL2SQL、不自动创建工单。

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/ask" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC" \
  -H "X-Company-Id: CSCEC" \
  -H "X-Mock-User-Id: demo-user" \
  -d "{\"message\":\"查询项目风险排名\",\"context\":{\"project_id\":\"P001\"}}"
```

如消息涉及停工、处罚、清退、限制作业等动作，响应会强制 `need_human_review=true`。

`execute_preview` 会读取 active prompt 并调用 Qwen 生成结构化路由解释；Qwen 未配置时安全降级为 `preview_status=llm_unavailable`，仍不执行 DAG 或工具。

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/ask" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC" \
  -H "X-Company-Id: CSCEC" \
  -H "X-Mock-User-Id: demo-user" \
  -d "{\"message\":\"查询项目风险排名\",\"execution_mode\":\"execute_preview\",\"context\":{\"project_id\":\"P001\"}}"
```

## Phase 2 Agent 2.4-C DAG Plan Only

`POST /api/v1/agent/ask` supports `execution_mode="plan_only"`. This mode returns an auditable DAG plan shape with `planned_steps`, `dag_status="planned"`, and `dag_execution_allowed=false`.

This is not real orchestration: it does not execute DAG nodes, does not call parallel agents, does not run tools, does not execute SQL, and does not create work orders. NL2SQL-related planned steps only reference the guarded `POST /api/v1/agent/nl2sql` gate.

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/ask" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC" \
  -H "X-Company-Id: CSCEC" \
  -H "X-Mock-User-Id: demo-user" \
  -d "{\"message\":\"sql list top 10 high risk projects\",\"execution_mode\":\"plan_only\",\"context\":{\"project_id\":\"P001\"}}"
```

## Phase 2 Agent 2.4-D Controlled DAG Executor

`POST /api/v1/agent/ask` now supports `execution_mode="dry_run"` and `execution_mode="controlled_execute"`.

- `dry_run` validates planned DAG steps, tool permissions, project scope, and human-review boundaries. It writes `agent_dag_run` and `agent_dag_step_run` audit rows, but executes no tools.
- `controlled_execute` can execute read-only tools only. Write-side tools return `approval_required`; restricted actions return `blocked`.
- No automatic work-order creation, dispatch, transition, closure, penalty, stop-work, or subcontractor removal is performed.

Dry-run example:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/ask" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: COMPANY-A" \
  -H "X-Company-Id: COMPANY-A" \
  -H "X-Mock-User-Id: demo-user" \
  -H "X-Scope-Type: project" \
  -H "X-Authorized-Project-Ids: P001" \
  -d "{\"message\":\"List open work orders for P001\",\"execution_mode\":\"dry_run\",\"context\":{\"project_id\":\"P001\"}}"
```

Controlled read-only example:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/ask" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: COMPANY-A" \
  -H "X-Company-Id: COMPANY-A" \
  -H "X-Mock-User-Id: demo-user" \
  -H "X-Scope-Type: project" \
  -H "X-Authorized-Project-Ids: P001" \
  -d "{\"message\":\"Check open work order status for P001\",\"execution_mode\":\"controlled_execute\",\"context\":{\"project_id\":\"P001\"}}"
```

## Phase 2 Agent 2.4-E Read-Only Tool Coverage

The controlled DAG executor can now execute these additional read-only tools:

- `profile.read`
- `rules.read_triggers`
- `hazards.read`
- `metrics.read_catalog`

All outputs are bounded summaries with explicit fields. The executor still does not run write-side actions. Work-order creation, dispatch, transition, hazard creation, stop-work, penalty, and subcontractor removal remain blocked or `approval_required`.

Example:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/agent/ask" \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: COMPANY-A" \
  -H "X-Company-Id: COMPANY-A" \
  -H "X-Mock-User-Id: demo-user" \
  -H "X-Scope-Type: project" \
  -H "X-Authorized-Project-Ids: P001" \
  -d "{\"message\":\"explain project profile risk score\",\"execution_mode\":\"controlled_execute\",\"context\":{\"project_id\":\"P001\"}}"
```
