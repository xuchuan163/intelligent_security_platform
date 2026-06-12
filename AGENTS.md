# AGENTS.md — 中建智慧安全平台 AI 协作规范

> 本文件是 vibe coding / Cursor Agent 的**首要上下文**。开始任何编码任务前必须先阅读本文件。

> **项目状态（2026-06-08）：Phase 0–5 核心里程碑已验收。** 一期已收口；**贝叶斯 L3** 已交付（`docs/PHASE5_BAYESIAN_L3_ACCEPTANCE.md`）；前端 **风险归因页** `/analysis/attribution` 已对接 `POST /analysis/attribution`。behavior_memory、视频/BIM、灾备实操等仍不在范围。详见 `docs/PROJECT_CLOSURE.md`。

---

## 1. 项目定位

**中建集团项目工地安全智能平台** — 以项目、工人、分包商三类安全风险画像为核心，结合强规则预警、工单闭环、指标语义层与 Agent 智能能力的施工安全管控平台。

| 项 | 内容 |
|---|---|
| 设计依据 | `技术参考文档/中建集团项目工地安全智能平台_技术开发文档_V1.6_记忆系统与上下文治理增强版.md`（V1.7） |
| 数据设计 | `技术参考文档/数据库数据表设计文档.md` |
| 接口设计 | `技术参考文档/接口设计文档.md` |
| 范围边界 | `docs/MVP_SCOPE.md` |
| 实施路线 | `docs/IMPLEMENTATION_ROADMAP.md` |
| 收口说明 | `docs/PROJECT_CLOSURE.md` |
| Vibe 分阶段执行 | `docs/VIBE_CODING_PLAYBOOK.md` |

---

## 2. 当前代码基线（截至 2026-06-08）

### 2.1 已实现

| 模块 | 状态 | 关键路径 |
|---|---|---|
| 后端框架 | ✅ | `backend/app/main.py` |
| MySQL 29 张 ORM 表 | ✅ | `backend/app/infrastructure/database/models.py` |
| Alembic 迁移链 | ✅ | `backend/alembic/versions/` |
| 三类画像 + 类型权重 + 动态因子 + 重算 | ✅ | `backend/app/services/profiles/` |
| 强规则 YAML + RuleEngine（10 条） | ✅ | `config/rules/`、`backend/app/services/rules/engine.py` |
| 规则触发日志 + 去重自动建单 | ✅ | `backend/app/services/rules/work_order_trigger.py` |
| 工单状态机 + 隐患上传流转 + 超期升级 | ✅ | `work_orders/`、`hazards.py`、`WorkOrdersPage.vue` |
| 指标语义层（100+ 指标） | ✅ | `metrics.py`、`config/metrics/catalog.yaml` |
| JWT + RBAC + OAuth 占位 | ✅ | `auth.py`、`core/rbac.py`、`LoginPage.vue` |
| 会话记忆 + NL2SQL 安全门 + 多 Agent DAG | ✅ | `memory.py`、`agent.py`、`Nl2SqlChatPage.vue` |
| 四库（Redis/Milvus/Neo4j 可选） | ✅ | `rag.py`、`graph.py`、`deploy/docker-compose.yml` |
| 贝叶斯 L2/L3 归因 + 版本 API | ✅ | `analysis.py`、`config.py`、`domain/bayesian/` |
| 事故案例库（200+ L3 种子） | ✅ | `cases.py`、`seed_cases_l3_bulk.py` |
| Qwen 安全助手 + 隐患整改 Agent | ✅ | `assistant.py`、`HazardRectificationPage.vue` |
| Vue3 前端 15 页（含风险归因） | ✅ | `frontend/src/pages/`、`AttributionAnalysisPage.vue` |
| 演示种子数据 | ✅ | `backend/scripts/seed_demo_data.py` |

### 2.2 明确未实现（不要擅自扩展）

- behavior_memory（培训向量，需合规签字）
- 视频 AI 实时告警、BIM 三维图层
- 灾备双活实操、生产 K8s / 全量 OAuth / WAF
- L4 时序/GNN、L3 在线自动重训 cron
- 分包商清退 / 自动处罚（必须人工复核）
- 生产级 OA 回写、自动处罚工单

详见 `docs/MVP_SCOPE.md`、`docs/PROJECT_CLOSURE.md`。

---

## 3. 目录结构与职责

```text
backend/
  app/
    api/v1/endpoints/     # 薄路由：参数校验 + 调用 service + 返回 success()
    core/                 # config、responses、errors
    domain/               # 纯业务规则（无 DB 依赖）：risk、work_orders
    infrastructure/       # DB session、LLM client
    schemas/              # Pydantic 请求/响应模型
    services/             # 业务逻辑（可测）
      profiles/
      work_orders/
      rules/
      metrics/
      agents/
      dashboard/
  alembic/versions/       # 数据库迁移（一表一迁移或逻辑分组）
  scripts/                # seed、运维脚本
  tests/                  # pytest：domain / services / api

frontend/
  src/
    api/client.ts         # Axios 封装，对齐后端 /api/v1
    pages/                # 页面组件
    types/api.ts          # TS 类型

docs/                     # 计划、规范、验收（给人和 AI 读）
config/                   # 规则、指标 YAML/JSON（二期）
prompts/                  # Agent Prompt 模板（二期）

技术参考文档/              # 设计说明书（只读参考，不直接改）
```

### 分层规则

1. **endpoint 不写业务逻辑**，只做 HTTP 适配；
2. **domain 不 import SQLAlchemy**，保持纯函数可单测；
3. **service 负责 DB 读写**，通过 `Session` 注入；
4. **schema 定义 API 契约**，请求体必须走 Pydantic；
5. **迁移只通过 Alembic**，禁止手改生产库。

---

## 4. 编码规范

### 4.1 Python 后端

- Python 3.11+，类型注解必须完整；
- 使用 `from app.xxx import yyy` 绝对导入；
- 数据库查询必须预留 `tenant_id` 过滤位（即使 MVP 暂未启用认证）；
- 新增 API 走 `app/core/responses.success()` 包装；
- 错误由 `app/core/errors.py` 统一处理，**禁止** endpoint 内裸抛未处理异常；
- 业务错误用 `HTTPException(status_code=..., detail="...")`，会自动映射业务错误码。

### 4.2 统一响应格式

**成功：**

```json
{
  "code": "SUCCESS",
  "message": "ok",
  "data": {}
}
```

**失败（已注册 handler）：**

```json
{
  "code": "40401",
  "message": "Project profile not found",
  "request_id": "uuid",
  "data": null,
  "timestamp": "2026-06-02T10:00:00+08:00"
}
```

### 4.3 前端

- Vue 3 Composition API + TypeScript；
- API 调用统一走 `frontend/src/api/client.ts`；
- 类型定义同步更新 `frontend/src/types/api.ts`；
- 不引入新 UI 框架，保持现有风格。

### 4.4 数据库

- 新表/改表：**先改 models.py → alembic revision → 迁移脚本**；
- 表名小写蛇形，业务主键 `{entity}_id`；
- 敏感字段：工人姓名脱敏、**禁止存身份证号原文/体检明细**；
- JSON 字段：`risk_tags`、`evidence` 用 list/dict，保持可序列化。

### 4.5 Git 提交

- 一次提交只做一件事；
- 不提交 `.env`、密钥、`node_modules`、`__pycache__`；
- 提交前跑：`pytest`（backend）、必要时 `npm run build`（frontend）。

---

## 5. 领域规则（不可违反）

### 5.1 风险分口径

源文件：`backend/app/domain/risk.py`

```text
最终风险分 = min(100, max(0, 基础分 × 动态修正系数 + 强规则触发分))
```

| 分值 | risk_level |
|---:|---|
| 0–30 | low |
| 31–60 | medium |
| 61–80 | high |
| 81–100 | critical |

### 5.2 强规则优先

以下场景**必须规则触发**，不得仅依赖 LLM 判断：

- 重大隐患超期未闭环 → SR-PROJ-001
- 特种设备超期未检仍使用 → SR-PROJ-004
- 特种作业证过期 → SR-WORKER-001

### 5.3 工单状态机

源文件：`backend/app/domain/work_orders.py`

合法转换见 `docs/MVP_SCOPE.md` 工单章节。**禁止**跳过状态或新增未文档化的 action。

### 5.4 Agent 边界

- LLM 输出**不得**作为处罚、清退、停工的唯一依据；
- 涉及停工、限制作业、清退 → 必须 `need_human_review: true`；
- 禁止向 LLM 传入：身份证、体检明细、人脸原图、原始视频；
- 关键结论必须引用 `evidence`（规则 ID、指标编码、记录 ID）。

### 5.5 多租户预留

所有新业务表/查询必须包含 `tenant_id`（及必要时 `org_path`），即使 MVP 使用固定值 `CSCEC-DEMO`。

---

## 6. AI 执行任务的标准流程

### 6.1 开始任务前

1. 阅读 `docs/MVP_SCOPE.md` 确认任务在范围内；
2. 阅读 `docs/IMPLEMENTATION_ROADMAP.md` 找到对应 Phase/Task；
3. 阅读相关设计文档章节；
4. 阅读要修改的文件及现有测试；
5. 若任务超出 MVP 范围，**先询问用户**而非直接实现。

### 6.2 实施顺序（TDD 优先）

```text
1. 写/更新失败测试（tests/）
2. 最小实现使测试通过
3. 运行 pytest -v 确认 GREEN
4. 更新 schema / 前端类型（如有 API 变更）
5. 更新相关 docs（仅当行为变化时）
```

### 6.3 完成任务后

- 运行 `pytest` 并贴出结果；
- 若有 API 变更，给出 curl 示例；
- 对照 `docs/IMPLEMENTATION_ROADMAP.md` 勾选对应 Task；
- **不要**声称完成而未跑测试。

---

## 7. 常用命令

```bash
# 后端
cd backend
pip install -e .
alembic upgrade head
python scripts/seed_demo_data.py
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pytest -v

# 前端
cd frontend
npm install
npm run dev

# 数据库（Docker）
docker compose -f deploy/docker-compose.yml up -d
```

---

## 8. 环境变量

见 `.env.example`：

| 变量 | 说明 |
|---|---|
| DATABASE_URL | MySQL 连接串 |
| REDIS_URL | Redis 连接串（默认 `redis://localhost:6379/0`，`deploy/docker-compose.yml` 已含 Redis） |
| DASHSCOPE_API_KEY | 阿里云 Qwen API Key（可选） |
| QWEN_MODEL | 默认 qwen-plus |
| QWEN_BASE_URL | DashScope 兼容端点 |

**禁止**把真实 Key 写入代码或提交到 Git。

---

## 9. 文件阅读优先级

接到任务时按此顺序加载上下文：

| 优先级 | 文件 | 何时读 |
|:---:|---|---|
| P0 | 本文件 `AGENTS.md` | 始终 |
| P0 | `docs/MVP_SCOPE.md` | 判断做不做 |
| P0 | `docs/IMPLEMENTATION_ROADMAP.md` | 判断怎么做、做到哪 |
| P0 | `docs/VIBE_CODING_PLAYBOOK.md` | 当前 Sprint、Session Prompt |
| P1 | `技术参考文档/接口设计文档.md` | 涉及 API |
| P1 | `技术参考文档/数据库数据表设计文档.md` | 涉及表结构 |
| P2 | `docs/plans/*.md` | 模块级详细计划 |
| P2 | 技术参考文档 V1.7 原文 | 需要业务背景时 |

---

## 10. 禁止事项清单

- ❌ 未读 MVP_SCOPE 就实现二期功能（Redis/Milvus/Neo4j/多 Agent/NL2SQL）
- ❌ 在 endpoint 写复杂业务逻辑
- ❌ 手改数据库不跑 Alembic
- ❌ 存储身份证号、体检明细到 MySQL 或传入 LLM
- ❌ Agent 自动创建停工/清退/处罚类工单（必须人工确认）
- ❌ 绕过 `tenant_id` 的全表扫描
- ❌ 修改与任务无关的文件
- ❌ 提交 `.env` 或密钥
- ❌ 无测试就宣称功能完成

---

## 11. 联系方式与决策

遇到以下情况**停止编码并询问用户**：

1. 需求与技术文档冲突；
2. 需要引入新中间件（Redis/Milvus/Neo4j/Kafka）；
3. 需要修改已发布 API 的 breaking change；
4. 测试无法跑通且无法判断是环境问题还是代码问题；
5. 任务估算超出当前 Phase 范围。

---

**版本：** 1.0 | **日期：** 2026-06-02
