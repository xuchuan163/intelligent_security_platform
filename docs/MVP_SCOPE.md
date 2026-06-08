# MVP 范围边界说明书

> 本文档定义 vibe coding 的**做 / 不做**边界。AI 和开发者开始任务前必须先确认任务落在本文档允许范围内。

| 项 | 内容 |
|---|---|
| 版本 | 1.0 |
| 日期 | 2026-06-02 |
| 依据 | 技术文档 V1.7 第 23.1 节「8 周 MVP 交付范围」 |
| 关联 | `docs/IMPLEMENTATION_ROADMAP.md`、`AGENTS.md` |

---

## 1. 一期 MVP 目标（8 周）

交付一个**本地可运行、可演示、可验收**的智慧安全平台，证明三类画像 + 强规则 + 工单闭环 + 驾驶舱 + 基础 Agent 的价值。

### 1.1 必须交付（In Scope）

| # | 模块 | MVP 交付内容 | 当前状态 |
|:---:|---|---|:---:|
| 1 | **项目画像** | 隐患+设备+进度压力简化评分，查询/排名/重算 | ✅ 已完成，API 契约已固化 |
| 2 | **工人画像** | 考核+违规+证书简化评分，查询 | ✅ 已完成，API 契约已固化 |
| 3 | **分包商画像** | 超期隐患+高风险工人占比+信用分，查询 | ✅ 已完成，API 契约已固化 |
| 4 | **强规则预警** | YAML 10 条 + 触发日志 + 重算自动工单 | ✅ 已完成 |
| 5 | **隐患闭环** | 隐患台账 + 整改建议（模板/Agent） | ⚠️ 缺 Agent 整改建议 |
| 6 | **工单流转** | 创建、状态机、列表、前端闭环操作、超期升级 API | ✅ 已完成 |
| 7 | **风险驾驶舱** | KPI + 项目 Top10 + 工单分布 | ✅ 基本完成 |
| 8 | **事故案例库** | 结构化导入（MySQL 表 + 种子） | ✅ 已完成，5 条种子 + `/case/list` |
| 9 | **数据治理** | 统一 ID、指标字典初版（≥30 指标） | ✅ metric_catalog 已有 32 条启用指标 |
| 10 | **会话记忆** | Redis 会话上下文（多轮问数） | ❌ 未开始 |
| 11 | **Qwen 助手** | 安全问答 + 项目风险解释 | ✅ 基本完成 |
| 12 | **认证预留** | mock 用户 + 部分 data_scope | ✅ mock 用户 + data_scope 读路径过滤 + 10 条权限测试 |

**图例：** ✅ 完成 | ⚠️ 部分完成 | ❌ 未开始

---

## 2. 明确不做（Out of Scope — MVP 阶段禁止实现）

以下能力**只允许预留目录/接口占位**，不得在 MVP Phase 完整实现：

| # | 模块 | 原因 | 何时做 |
|:---:|---|---|---|
| 1 | Neo4j 图谱落库 | 复杂度高，MySQL 可满足 MVP | Phase 3 |
| 2 | Milvus 向量 RAG | 依赖知识库清洗 | Phase 3 |
| 3 | Redis 集群 / 长任务 Checkpoint | 二期记忆系统 | Phase 2 |
| 4 | 完整 NL2SQL + SQL 审计 | 依赖指标语义层成熟 | Phase 2 |
| 5 | 6 Agent DAG 编排（LangGraph） | 依赖单 Agent 验证 | Phase 2 |
| 6 | 贝叶斯归因 / 风险预测 | 案例 < 50 条无意义 | Phase 4 |
| 7 | 视频 AI 实时告警 | 需边缘部署 | Phase 4 |
| 8 | BIM 三维风险图层 | MVP 仅二维热力图占位 | Phase 3 |
| 9 | 生产级 OAuth2 / WAF / K8s | 试点后用 | Phase 3 |
| 10 | 工人 behavior_memory | 需合规治理 | Phase 2 末 |
| 11 | 分包商清退 / 自动处罚 | 必须人工复核 | 永不自动 |
| 12 | 时序库 InfluxDB/TDengine | IoT 接入后 | Phase 3 |

---

## 3. 模块级边界详述

### 3.1 三类画像

| 项 | MVP | 二期 |
|---|---|---|
| 维度数 | 简化 3–4 因子 | 项目 10 维度 / 工人 6 维度 / 分包商 9 维度 |
| 动态修正系数 | 固定 1.0 | DF-SCH/DF-WEA/DF-HZD 等因子表 |
| 历史快照 | 无 calc_date | 按日快照 + 趋势 |
| 重算 API | 三类 POST /profile/recalculate | 事件触发 |
| 项目类型差异化权重 | 统一权重 | 房建/市政/基建矩阵 |
| 输出 | 分+等级+标签+证据 | +维度分+解释+建议+置信度 |

**MVP 允许：** 在 `calculator.py` 优化公式，但不引入动态因子表。

### 3.2 强规则引擎

| 项 | MVP | 二期 |
|---|---|---|
| 规则存储 | `config/rules/*.yaml` + `RuleEngine` | 独立微服务（二期） |
| 规则数量 | 10 条 | 30+ 条（附录 B 全量） |
| 触发方式 | 画像计算时同步 | 独立 rule-engine-service |
| 工单联动 | 手动创建 + 规则触发去重自动建单 | 外部系统推送 |
| 日志 | rule_trigger_log 表 | + 审计 + Webhook |

**MVP 必须做：** 规则 YAML + 引擎 + 10 条强规则已完成，覆盖项目、工人、分包商。

### 3.3 工单系统

| 项 | MVP | 二期 |
|---|---|---|
| 状态 | 7 态状态机 | 同左 + 外部 OA 映射 |
| 类型 | 7 种 work_order_type | 同左 |
| 升级 | overdue_escalated 状态 | 三级升级 + escalation_history |
| 附件 | 无 | attachments JSON |
| 前端 | 列表 + 创建/确认/流转操作 | 移动端和附件增强 |
| 外部回写 | 无 | OA/企业微信 Webhook |

**MVP 必须做：** 前端工单确认/流转 + PATCH status API + 手动超期升级 API 已完成。

### 3.4 指标语义层

| 项 | MVP | 二期 |
|---|---|---|
| 存储 | metric_catalog 表 + seed 数据 | 完整 CRUD + 版本管理 |
| API | GET /metrics/catalog、/{code} 已接 DB | + validate、lineage、aliases |
| 指标数 | 当前 32 条核心指标定义 | ≥ 100 |
| NL2SQL | 不做 | 100+ 测试集 + SQL 审计 |

**MVP 必须做：** metric_catalog 表、迁移、catalog API 和 ≥30 条种子指标已完成。

### 3.5 Agent

| 项 | MVP | 二期 |
|---|---|---|
| Agent 数 | 1（SafetyAssistant） | 6 核心 Agent |
| 编排 | 无 DAG | 主控 Agent + 并行/串行 |
| 记忆 | 无 Redis | L1 会话 + L2 Checkpoint |
| Prompt 版本 | 硬编码 SYSTEM_PROMPT | agent_prompt_version 表 |
| 反馈 | 无 | agent_feedback 表 |
| 模型 | Qwen qwen-plus | + 本地私有化模型 |

**MVP 允许：** 优化 SafetyAssistant 的 Prompt 和 evidence 引用格式。

### 3.6 认证与权限

| 项 | MVP | 二期 |
|---|---|---|
| 认证 | 无（开放 API） | 集团 OAuth2 + JWT |
| 授权 | 无 | RBAC + data_scope |
| 租户 | 固定 CSCEC-DEMO | 多租户隔离 |
| 敏感字段 | 代码层禁止 | + API 层脱敏过滤 |

**MVP 必须做：** `app/core/security.py` 的 `get_current_user()` + `apply_data_scope`；补齐 dashboard/metrics 等读路径与 10 条权限测试。

### 3.7 前端

| 页面 | MVP | 说明 |
|---|---|---|
| 驾驶舱 Dashboard | ✅ | KPI + 排名 + 工单分布 |
| 项目/工人/分包商画像 | ✅ | 详情页 |
| 工单列表 | ✅ | 已支持创建和闭环操作 |
| AI 助手 | ✅ | 对话 |
| 规则触发日志 | ✅ | `/rules/triggers` |
| 指标目录浏览 | ✅ | `/metrics` |
| 移动端 | ❌ | 二期 |

---

## 4. 数据范围

### 4.1 MVP 演示数据规模

| 对象 | 数量 | 来源 |
|---|---:|---|
| 租户 | 1 | CSCEC-DEMO |
| 项目 | 3 | seed_demo_data.py |
| 分包商 | 3 | 同上 |
| 工人 | 8 | 同上 |
| 隐患 | 4 | 同上 |
| 设备 | 3 | 同上 |
| 工单 | 1 | 同上 |
| 规则触发 | 1 | 同上 |

### 4.2 上游系统

MVP **不对接**真实上游系统，所有数据来自：

- `seed_demo_data.py` 本地种子；
- 后续 `scripts/seed/` 扩展；
- Mock JSON 文件（`backend/tests/fixtures/`）。

---

## 5. 技术栈边界

### 5.1 MVP 允许依赖

**后端：** Python 3.11、FastAPI、SQLAlchemy 2.x、Alembic、Pydantic、PyMySQL、pytest、httpx

**前端：** Vue 3、Vite、TypeScript、ECharts、Axios

**基础设施：** MySQL 8.0（Docker）、Docker Compose

**LLM：** 阿里云 DashScope Qwen（可选，无 Key 时降级）

### 5.2 MVP 禁止引入（除非用户明确批准）

- Redis、Neo4j、Milvus、Kafka、InfluxDB
- Celery、Airflow、DolphinScheduler
- LangGraph、LangChain（二期评估）
- 新前端框架（React、Angular）
- 微服务拆分（保持单体 FastAPI）

---

## 6. API 范围

### 6.1 MVP 应有接口

| 方法 | 路径 | 状态 |
|---|---|:---:|
| GET | /api/v1/health | ✅ |
| GET | /api/v1/dashboard/overview | ✅ |
| GET | /api/v1/profile/project/{id} | ✅ |
| GET | /api/v1/profile/worker/{id} | ✅ |
| GET | /api/v1/profile/subcontractor/{id} | ✅ |
| GET | /api/v1/profile/ranking/projects | ✅ |
| POST | /api/v1/profile/recalculate | ✅ 三类画像 |
| GET | /api/v1/rules/triggers | ✅ |
| GET | /api/v1/work-orders | ✅ |
| POST | /api/v1/work-orders | ✅ |
| PATCH | /api/v1/work-orders/{id}/status | ✅ |
| POST | /api/v1/assistant/chat | ✅ |
| POST | /api/v1/assistant/project-risk-explanation | ✅ |
| GET | /api/v1/metrics/catalog | ✅ |
| GET | /api/v1/metrics/{metric_code} | ✅ |

### 6.2 MVP 不应新增

- `/api/v1/agent/ask`、`/agent/nl2sql`
- `/api/v1/memory/*`
- `/api/v1/case/*`
- `/api/v1/report/*`
- `/webhook/*`

如需占位，返回 `501 Not Implemented` 并注明 Phase 2。

---

## 7. 验收标准（MVP 试点）

来源于技术文档第 23.5、24.1 节，MVP 演示必须满足：

| # | 指标 | 目标 |
|:---:|---|---|
| 1 | 数据源接入（模拟） | ≥ 5 类（项目/工人/隐患/设备/分包） |
| 2 | 项目画像覆盖 | 试点项目 100% |
| 3 | 分包商画像覆盖 | 主要分包商 ≥ 90% |
| 4 | 工人画像覆盖 | 在场工人 ≥ 80% |
| 5 | 强规则 | ≥ 10 条可配置 |
| 6 | 工单闭环率 | 演示流程可完成 confirm→closed |
| 7 | 演示能力 | 大屏 + 画像 + 工单 + 助手问答 |
| 8 | 画像查询 P95 | ≤ 800ms（本地） |
| 9 | 强规则可解释率 | 100%（evidence 字段非空） |
| 10 | 后端测试 | pytest 全绿 |

---

## 8. 决策原则

当需求不明确时，按以下优先级决策：

```text
1. 本文档 MVP_SCOPE（范围边界）
2. IMPLEMENTATION_ROADMAP（阶段优先级）
3. 数据库/接口设计说明书（契约）
4. 技术文档 V1.7（业务背景）
5. 现有代码实现（保持一致）
```

**冲突处理：**

- 技术文档要求二期能力，但 MVP_SCOPE 标注不做 → **不做**，可留 TODO；
- 代码现状与设计文档不一致 → **优先改代码对齐设计**，除非用户指定保留；
- 用户口头要求与 MVP_SCOPE 冲突 → **询问确认**。

---

## 9. 变更流程

如需扩大或缩小 MVP 范围：

1. 用户明确批准；
2. 更新本文档对应章节；
3. 同步更新 `IMPLEMENTATION_ROADMAP.md`；
4. 再开始编码。

---

**文档结束**
