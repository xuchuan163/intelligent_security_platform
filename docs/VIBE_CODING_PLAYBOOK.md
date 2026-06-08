# Vibe Coding 执行手册

> AI 每次开工必读：`AGENTS.md` → 本文件「当前 Sprint」→ 对应 `docs/plans/XX-*.md` → `docs/MVP_SCOPE.md`

| 项 | 内容 |
|---|---|
| 版本 | 1.1 |
| 日期 | 2026-06-03 |
| 审计基准 | 仓库代码 + `pytest` 测试清单 |
| 设计原文 | `技术参考文档/中建集团项目工地安全智能平台_技术开发文档_V1.6_记忆系统与上下文治理增强版.md`（正文 V1.7） |

---

## 1. 文档优先级（冲突裁决）

```text
AGENTS.md > docs/MVP_SCOPE.md > docs/IMPLEMENTATION_ROADMAP.md > 技术参考文档 §23
```

| 冲突点 | 执行口径 |
|---|---|
| §23.1 含 Redis 会话记忆 | **Phase 2** 再做（MVP 禁止 Redis） |
| §26.2 P0「主控+问数 Agent」 | **Phase 2**；Phase 1 仅 `SafetyAssistant` |
| §26.2 P0「统一认证」 | Phase 1 用 `core/security.py` mock + `data_scope` |

---

## 2. 实现状态审计（2026-06-03）

### Phase 0 — 100% ✅

脚手架、15 表、三类画像、核心 API、错误响应、前端 6 页、Docker MySQL、种子、Qwen 助手均已就绪。

### Phase 1 — 100% ✅

| 模块 | 已完成 | 未完成 |
|---|---|---|
| **1.1 规则引擎** | YAML 10 条、engine、calculator、trigger_log、规则→自动工单 | 30+ 全量规则（二期） |
| **1.2 指标语义层** | `metric_catalog` 表、DB API、`catalog.yaml`、seed 32 条 | 前端页（可选，非 Phase 1 门禁） |
| **1.3 画像增强** | 三类 recalculate、DB `confidence_level`、服务层返回、API 契约 `calculated_at` / `confidence_level` | 历史快照趋势（二期） |
| **1.4 工单闭环** | 前端全流程、创建、规则自动工单、超期升级 API | 定时任务（二期） |
| **1.5 认证预留** | `get_current_user`、`/auth/me`、画像/工单/dashboard/rules `data_scope`、metrics 接入 mock 用户上下文、**10 条**权限测试 | JWT / OAuth2（二期/三期） |
| **1.6 案例库** | `accident_case_library` 表迁移、5 条结构化种子、GET `/case/list` | Milvus/RAG（二期/三期） |
| **1.7 测试文档** | API smoke、OpenAPI、README、验收文档、`profile_algo_20.jsonl`、全量验证 | Phase 2 方案评审 |

**代码证据（已实现）：**

- 规则：`config/rules/*.yaml`（10 条）、`services/rules/engine.py`、`work_order_trigger.py`
- 画像重算：`POST /api/v1/profile/recalculate`（三类 + org_scope）
- 认证：`backend/app/core/security.py`（`MockUser`、`apply_data_scope`）
- 工单前端：`frontend/src/pages/WorkOrdersPage.vue`（confirm → closed）
- 指标：seed **32** 条，`GET /metrics/catalog` 接 DB
- 案例：`accident_case_library` + 5 条种子，`GET /api/v1/case/list`

### Phase 2 — 100% ✅

| 模块 | 已完成 |
|---|---|
| 2.1 记忆 | Redis L1、session API、checkpoint、Agent `session_id` 桥接 |
| 2.2 指标增强 | validate / lineage / aliases、100 指标种子 |
| 2.3 NL2SQL | 审计、执行、澄清、105-case benchmark、API gate |
| 2.4 多 Agent | 六路路由、DAG dry/controlled、审批队列、人工执行、feedback |
| 2.5 隐患顾问 | evidence 建议、审批开单、`/agent/hazard-advisor` 演示模式 |

**验收：** `docs/PHASE2_ACCEPTANCE.md`（85 项门禁 pytest 全绿）

### Phase 3 — 100% ✅

**验收：** `docs/PHASE3_ACCEPTANCE.md`（六项门禁、337 pytest、四库 health）

### Phase 4 — 100% ✅

**验收：** `docs/PHASE4_ACCEPTANCE.md`（397 pytest、权重/回测/压测/贝叶斯 L2）

### 项目收口 — 最终状态 ✅

**不再实施延后扩展**（L3 贝叶斯、behavior_memory、视频/BIM、灾备实操等）。  
**闭环说明与演示路径：** `docs/PROJECT_CLOSURE.md`

---

## 3. Phase 1 Sprint 执行结果

### Sprint A — 指标 30 条（阻塞 NL2SQL/演示口径）

| Task | 计划文件 | 状态 |
|:---:|---|:---:|
| 1.2.2 + 1.2.3 | `docs/plans/01-metric-semantic.md` | ✅ |

### Sprint B — 强规则 10 条

| Task | 计划文件 | 状态 |
|:---:|---|:---:|
| 1.1.6 | `docs/plans/02-rule-engine-expand.md` | ✅ |

### Sprint C — 画像契约 + 工单超期 + 权限补全

| Task | 计划文件 | 状态 |
|:---:|---|:---:|
| 1.3.3、1.3.4、1.4.5、1.5.2、1.5.3 | `03-profile-api.md`、`04-work-order-overdue.md`、`05-auth-scope.md` | ✅ |

### Sprint D — 事故案例库 MVP

| Task | 计划文件 | 状态 |
|:---:|---|:---:|
| 1.6.1–1.6.3 | `docs/plans/06-accident-case.md` | ✅ |

### Sprint E — Phase 1 验收收口

| Task | 计划文件 | 状态 |
|:---:|---|:---:|
| 1.7.1–1.7.4、1.2.5（可选） | 本文件 §6 验收清单 | ✅ |

### Sprint F — 隐患上传工单闭环增强

| Task | 计划文件 | 状态 |
|:---:|---|:---:|
| 1.4.x 隐患上传、岗位流转、附件闭环、验收脚本 | `docs/plans/工单改造参考文档.md` | ✅ |

**可演示命令：**

```bash
cd backend
..\.venv\Scripts\python.exe scripts\verify_hazard_workflow_demo.py
```

**Phase 1 出口门禁：** `docs/ACCEPTANCE_CRITERIA.md` + 路线图「Phase 1 里程碑」全部勾选。

---

## 4. Phase 2–4 任务安排（Phase 1 通过后执行）

### Phase 2：Agent 与智能问数（8 周，需用户批准 Redis）

| 周次 | Task 块 | 关键交付 |
|:---:|---|---|
| W1 | 2.1.1–2.1.2 | Docker Redis、L1 会话 Key |
| W2 | 2.1.3–2.1.5 | session 归档 API、`agent_task_checkpoint` |
| W3 | 2.2.1–2.2.3 | validate / lineage / aliases |
| W4–W5 | 2.3.1–2.3.5 | NL2SQL 审计 + `nl2sql_100.jsonl` |
| W6–W7 | 2.4.1–2.4.6 | 6 Agent Prompt、`POST /agent/ask`、feedback |
| W8 | 2.5.1–2.5.3 | 隐患整改 Agent + 人工 confirm 工单 |

详细步骤：`docs/plans/07-phase2-agent-memory.md`

### Phase 3：四库与集成（8 周，评审后执行）

| 子阶段 | 内容 | 计划章节 |
|:---:|---|---|
| 3-A | JWT / RBAC | `08-phase3` §3 |
| 3-B | Redis 业务缓存 | §4 |
| 3-C | Milvus RAG | §5（推荐 Sprint 1） |
| 3-D | Neo4j 图谱（可延后） | §6 |
| 3-E | 报告 + Webhook | §7 |
| 3-F | 报告页 + 移动端 | §8 |

详细步骤：`docs/plans/08-phase3-four-libraries-integration.md`  
开工前必读：`docs/PHASE3_KICKOFF_AGENDA.md`（中间件批准表决）

### Phase 4：算法与推广（8 周，评审后执行）

| 子阶段 | 内容 | 计划章节 |
|:---:|---|---|
| 4-A | 项目类型权重 + 动态修正因子 | `09-phase4` §3 |
| 4-B | 案例 ≥50 + 回测评测 | §4（推荐 Sprint 1 并行） |
| 4-C | 100/500/2000 项目压测 | §5 |
| 4-D | 贝叶斯 L2（案例 ≥50，可选） | §6 |
| 4-E | behavior_memory（合规后，可选） | §7 |
| 4-F/G | 视频/BIM 占位、灾备文档 | §8 |

详细步骤：`docs/plans/09-phase4-algorithm-and-scale.md`  
开工前必读：`docs/PHASE4_KICKOFF_AGENDA.md`（案例量 / 合规表决）

---

## 5. 标准 Session Prompt（复制到 Cursor）

```markdown
# 任务
执行 IMPLEMENTATION_ROADMAP Task 【填写编号，如 1.2.2】。

# 必读（按序）
1. AGENTS.md
2. docs/VIBE_CODING_PLAYBOOK.md §3 当前 Sprint
3. docs/plans/【对应计划文件】
4. docs/MVP_SCOPE.md §【相关章节】

# 修改前阅读
【列出 2–5 个具体文件路径】

# 约束
- TDD：先失败测试再实现
- 查询带 tenant_id；endpoint 不写业务逻辑
- 禁止：Redis / Neo4j / Milvus / 多 Agent DAG / LangGraph

# 完成定义
- `cd backend && pytest -v` 全绿（贴摘要）
- 勾选 IMPLEMENTATION_ROADMAP 对应 Task
- 如有 API：附 curl 示例
```

---

## 6. Phase 1 验收勾选表

- [x] 10 条强规则 YAML 可触发（`pytest tests/services/test_rule_engine.py`）
- [x] `metric_catalog` ≥ 30 条（`GET /api/v1/metrics/catalog?page_size=50`）
- [x] 三类 `POST /profile/recalculate` 返回计数 + org_scope 测试通过
- [x] 工单前端可演示至 `closed`
- [x] `processing` 超期 → `overdue_escalated`（API 或脚本触发）
- [x] `GET /api/v1/case/list` 返回 ≥ 5 条种子案例
- [x] 权限测试 ≥ 10 条（`test_auth_mock` + `test_data_scope` + 新增）
- [x] `pytest -v` 全绿；`python scripts/check_db_schema.py` 通过

---

## 7. 技术文档章节索引

| 章节 | Phase | 对应 Task |
|---|---|---|
| §6–9 三类画像 | 0–1 | 1.3.x |
| §10 指标语义层 | 1–2 | 1.2.x、2.2.x |
| 附录 B 强规则 | 1 | 1.1.x |
| §15–16 记忆/工单 | 1–2 | 1.4.5、2.1.x |
| §17 案例库 | 1 | 1.6.x |
| §13–14 Agent | 2 | 2.4.x、2.5.x |
| §11 四库 | 3 | Phase 3 |
| §18 贝叶斯 | 4 | Phase 4 |

---

**维护：** 项目已收口（`docs/PROJECT_CLOSURE.md`），本文档与路线图仅作历史参考；新功能需新开项目评审。
