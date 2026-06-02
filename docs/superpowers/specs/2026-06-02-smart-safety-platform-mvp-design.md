# 中建智慧安全平台全栈 MVP 设计文档

日期：2026-06-02

## 背景

本项目面向中建集团项目工地安全管理，参考 `技术参考文档/中建集团项目工地安全智能平台_技术开发文档_V1.6_记忆系统与上下文治理增强版.md` 中的 V1.7 技术方案落地。当前目录尚无代码工程，因此一期目标是从零生成一个低耦合、可运行、可演示、便于后续扩展的全栈 MVP。

用户已确认采用 A 路线：全栈 MVP。

## 目标

一期交付一个本地可运行的智慧安全平台工程，覆盖以下能力：

1. 三类安全风险画像：项目、工人、分包商。
2. 强规则预警：重大隐患超期、无证作业、设备超期、危大工程未审批等高确定性风险。
3. 隐患与工单闭环：预警建议可转为工单，工单支持派发、处理中、待复核、关闭等状态。
4. 风险驾驶舱：展示项目风险排行、风险等级分布、工单状态和关键指标。
5. Qwen 安全助手：使用阿里云 `qwen-plus` 生成风险解释、整改建议和报告草稿。
6. MySQL 建库与示例数据：使用 Alembic 迁移和初始化脚本生成可演示数据。

## 非目标

以下能力只预留接口或目录边界，不在一期强制实现：

1. Neo4j 图谱实体关系落库。
2. Milvus 深度 RAG、事故案例向量检索和行为摘要记忆。
3. Redis 集群会话记忆和长任务状态恢复。
4. 完整 NL2SQL 与多 Agent DAG 编排。
5. 视频 AI 实时告警、BIM 三维风险图层、贝叶斯归因模型。
6. 生产级统一认证、WAF、K8s 高可用和灾备。

## 技术栈

后端：

- Python 3.11+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic Settings
- PyMySQL
- pytest

前端：

- Vue 3
- Vite
- TypeScript
- ECharts
- Axios

部署与本地开发：

- MySQL 8
- Docker Compose
- `.env` 配置文件
- `README.md` 启动说明

## 目录设计

```text
backend/
  alembic/
  app/
    api/
      v1/
        endpoints/
    core/
    domain/
    infrastructure/
      database/
      llm/
    schemas/
    services/
      profiles/
      rules/
      work_orders/
      agents/
  scripts/
  tests/

frontend/
  src/
    api/
    components/
    layouts/
    pages/
    router/
    stores/
    types/
  index.html

deploy/
  docker-compose.yml

docs/
  superpowers/
    specs/
    plans/
```

分层原则：

- `api` 只负责 HTTP 入参、出参和状态码。
- `services` 承载业务流程，如画像计算、规则触发、工单状态流转和 Agent 调用。
- `domain` 放业务实体、枚举、纯计算规则和不依赖框架的领域逻辑。
- `infrastructure` 封装数据库、LLM 客户端等外部依赖。
- 前端按页面和可复用组件拆分，避免把所有业务逻辑写进单个页面。

## 数据模型

一期使用 MySQL 作为唯一事实主库。核心表：

- `tenant`：租户或组织域。
- `project`：项目主数据，包含 `tenant_id`、`org_path`、项目类型、施工阶段。
- `subcontractor`：分包商主数据。
- `worker`：工人主数据，敏感信息只保留脱敏展示字段。
- `hazard`：隐患记录，包含等级、责任单位、整改截止时间、闭环状态。
- `equipment`：设备台账，包含检验有效期和使用状态。
- `project_risk_profile`：项目画像结果。
- `worker_risk_profile`：工人画像结果。
- `subcontractor_risk_profile`：分包商画像结果。
- `rule_trigger_log`：强规则触发日志。
- `safety_work_order`：安全工单。
- `agent_task_log`：Qwen 调用和输出摘要审计。

所有业务事实表和画像表必须包含 `tenant_id`。涉及项目范围的数据同时包含 `project_id` 或 `org_path`，为后续多租户和组织域过滤保留基础。

## 风险计算

统一公式：

```text
最终风险分 = min(100, 基础加权风险分 × 动态修正系数 + 强规则触发分)
```

风险等级：

- `low`：0-30
- `medium`：31-60
- `high`：61-80
- `critical`：81-100

一期计算策略：

- 项目画像：隐患整改风险、设备机械风险、工期/作业压力轻量指标、强规则触发分。工期/作业压力一期基于演示数据字段计算，二期替换为进度计划、作业票和考勤系统接入。
- 工人画像：考试风险、违规行为风险、证书有效性风险、作业限制规则。
- 分包商画像：隐患整改表现、所属工人高风险占比、事故/违规信用轻量指标。事故/违规信用一期基于演示数据字段计算，二期替换为事故案例库和历史履约数据。

每次画像计算写入解释明细字段，包括风险标签、关键证据、数据完整度、是否建议人工复核。

## 强规则

一期内置规则：

1. 重大隐患超期未闭环：加 20 分，风险等级至少 `high`，生成督办工单建议。
2. 无证特种作业：加 25 分，风险等级至少 `high`，建议限制作业并人工复核。
3. 危大工程未审批施工：加 30 分，风险等级至少 `critical`，建议停工核查。
4. 特种设备超期未检仍使用：加 25 分，风险等级至少 `high`，生成设备核查工单建议。
5. 新增事故或险情：加 30 分，建议专项复盘。

强规则优先于 LLM 判断。Qwen 可以解释规则命中原因，但不能覆盖规则结论。

## 工单闭环

工单状态：

- `pending_confirm`
- `dispatched`
- `processing`
- `waiting_review`
- `closed`
- `rejected`
- `overdue_escalated`

一期接口支持：

- 创建工单。
- 查询工单列表和详情。
- 更新工单状态。
- 根据规则触发日志生成工单建议。

涉及停工、限制作业、清退、处罚等管理动作时，系统只生成建议，必须保留人工确认状态。

## Qwen 接入

模型：阿里云 `qwen-plus`。

实现边界：

- 使用 OpenAI 兼容接口封装 Qwen 客户端。
- API Key 从环境变量读取，不写入业务代码。
- Agent 输出必须带事实依据摘要、置信度和人工复核建议。
- 高风险结论以数据库事实和强规则为准。
- 用户输入作为不可信内容处理，不允许覆盖系统提示词或工具权限。

一期 Agent 能力收敛为一个 `SafetyAssistantService`：

- `explain_project_risk(project_id)`
- `suggest_hazard_rectification(hazard_id)`
- `draft_weekly_report(project_id)`
- `chat(message, context)`

## API 设计

统一响应：

```json
{
  "code": "SUCCESS",
  "message": "ok",
  "data": {}
}
```

核心接口：

- `GET /api/v1/health`
- `GET /api/v1/dashboard/overview`
- `GET /api/v1/profile/project/{project_id}`
- `GET /api/v1/profile/worker/{worker_id}`
- `GET /api/v1/profile/subcontractor/{subcontractor_id}`
- `GET /api/v1/profile/ranking/projects`
- `POST /api/v1/profile/recalculate`
- `GET /api/v1/rules/triggers`
- `GET /api/v1/work-orders`
- `POST /api/v1/work-orders`
- `PATCH /api/v1/work-orders/{work_order_id}/status`
- `POST /api/v1/assistant/chat`
- `POST /api/v1/assistant/project-risk-explanation`

## 前端设计

页面：

- 驾驶舱：首页展示风险概览、项目排行、工单状态、风险等级分布。
- 项目画像：项目风险分、风险标签、规则命中、建议动作。
- 工人画像：工人风险等级、证书状态、培训/违规风险。
- 分包商画像：分包商风险等级、整改表现、高风险工人占比。
- 工单看板：工单筛选、状态更新、超期标识。
- 安全助手：Qwen 问答、风险解释和报告草稿。

视觉原则：

- 面向安全管理人员，采用稳定、清晰、信息密度适中的后台风格。
- 不做营销型首页。
- 不使用大面积单色渐变和装饰性背景。
- 图表和列表优先服务扫描、对比和督办。

## 配置与安全

`.env.example` 提供配置项：

```text
APP_ENV=local
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/cscec_safety
DASHSCOPE_API_KEY=replace-me
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

实际密钥和数据库密码由本地 `.env` 提供。仓库不提交 `.env`。

安全建议：

- 用户已在对话中暴露过阿里云 Key，建议在阿里云控制台轮换。
- 本地 MySQL root 密码仅用于开发环境；生产环境应使用最小权限账号。
- LLM 调用日志只记录摘要和任务 ID，不记录完整敏感输入。

## 测试策略

后端测试：

- 风险等级计算。
- 强规则触发和升档。
- 工单状态流转。
- Qwen 客户端在无 Key 时降级返回可解释错误。
- 主要 API 路由 smoke tests。

前端验证：

- 构建通过。
- 页面无明显布局溢出。
- API 客户端类型与后端响应保持一致。

实施时遵循 TDD：领域计算、规则和工单状态流转先写失败测试，再实现。

## 验收标准

1. `docker compose` 可启动 MySQL。
2. 后端迁移可创建数据库表。
3. 初始化脚本可导入演示数据。
4. 后端测试通过。
5. 前端构建通过。
6. 浏览器可访问驾驶舱、画像、工单和安全助手页面。
7. 风险画像和强规则结果可在前端展示，并可追溯到规则或数据证据。
