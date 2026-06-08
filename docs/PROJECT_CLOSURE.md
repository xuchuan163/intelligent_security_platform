# 项目收口说明（PROJECT_CLOSURE）

| 项 | 内容 |
|---|---|
| 原收口日期 | 2026-06-08（Phase 0–4） |
| **L3 解冻日期** | **2026-06-08** |
| 当前状态 | **Phase 0–4 已验收；Phase 5 贝叶斯 L3 重新立项进行中** |
| 分支 | `feature/phase5-bayesian-l3` |
| 验收依据 | `docs/PHASE2_ACCEPTANCE.md`、`docs/PHASE3_ACCEPTANCE.md`、`docs/PHASE4_ACCEPTANCE.md`、`docs/PHASE5_BAYESIAN_L3_KICKOFF.md` |

---

## 1. Phase 0–4 收口决议（保持不变）

经 Phase 0–4 全部核心里程碑验收，**一期交付物已闭环**。以下项在**一期范围内**不再实施：

| 原延后项 | 一期处置 |
|---|---|
| behavior_memory（培训向量） | **不做**（无合规签字） |
| 视频 AI / BIM 三维 | **不做** |
| 灾备双活实操 | **不做**（仅保留目标文档占位） |
| 生产 K8s / 全量 OAuth / 自动处罚清退 | **不做** |

---

## 2. L3 冻结解除（Phase 5 重新立项）

经 `docs/PHASE5_BAYESIAN_L3_KICKOFF.md` 专项评审表决，**贝叶斯 L3 单独立项**，不再属于「永久不做」：

| 项 | 内容 |
|---|---|
| 立项范围 | L3-0 门禁 → L3-A DAG/CPT 冷启动 → L3-B 案例标注与 200+ 训练集（Sprint 1） |
| 后续 Sprint | L3-C 训练、L3-D 推理、L3-E API、L3-F 验收（见实施计划） |
| 数据门禁 | 活跃案例 ≥ **200**（`check_bayesian_l3_gate.py`） |
| 合规 | 全路径 `need_human_review: true`；不得作为处罚/清退/停工唯一依据 |

**本期仍不做：** L4 时序/GNN、在线自动重训 cron、L3 驱动自动处罚工单。

---

## 3. 业务闭环（已成立，L3 为增强层）

```text
多源数据 / 演示种子
    ↓
指标语义层 + 三类画像（项目 / 工人 / 分包商）
    ↓
强规则引擎（YAML）→ 触发日志 → 自动工单（去重）
    ↓
隐患台账 → 整改建议（Agent）→ 工单状态机 → 复查闭环
    ↓
画像重算（含类型权重 / 动态因子）→ 驾驶舱 / 报告
    ↓
事故案例库（≥50 L2 / ≥200 L3）→ 回测评测 → RAG 检索
    ↓
智能能力：会话记忆、NL2SQL 安全门、多 Agent 受控编排
    ↓
贝叶斯 L2 归因（已交付）→ **L3 DAG+CPT（Phase 5 进行中）**
```

---

## 4. 交付能力清单

| 层级 | 能力 | 关键入口 |
|---|---|---|
| 数据 | MySQL 29 表、指标目录 100+、案例 ≥200（L3 种子） | `metric_catalog`、`accident_case_library` |
| 画像 | 三类查询/排名/重算、类型权重、动态因子 | `/api/v1/profile/*` |
| 规则 | 10+ YAML、触发日志、自动工单 | `/api/v1/rules/triggers` |
| 工单 | 状态机、超期升级、隐患联动 | `/api/v1/work-orders` |
| 智能 | 记忆、NL2SQL 门、Agent DAG、隐患顾问 | `/api/v1/agent/*`、`/api/v1/memory/*` |
| 四库 | Redis 缓存、Milvus RAG、Neo4j 邻居（可选） | `/api/v1/rag/*`、`/api/v1/graph/*` |
| 认证 | JWT、RBAC、OAuth 占位 | `/api/v1/auth/*` |
| 算法 | 案例回测、贝叶斯 L2 归因、**L3 结构/标注（Sprint 1）** | `/api/v1/analysis/attribution`、`config/bayesian/` |
| 前端 | 驾驶舱、画像、工单、Agent、报告等 | `frontend/` `npm run build` |

---

## 5. 质量门禁

```bash
cd backend && py -3.12 scripts/check_db_schema.py
cd backend && py -3.12 -m pytest -q
cd backend && py -3.12 scripts/check_bayesian_l3_gate.py --tenant-id CSCEC
cd frontend && npm run build
```

---

## 6. 演示最小路径（5 分钟）

```bash
docker compose -f deploy/docker-compose.yml up -d
cd backend && alembic upgrade head && python scripts/seed_demo_data.py
python -m uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

**L2 归因示例：**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analysis/attribution \
  -H "Content-Type: application/json" \
  -H "X-Mock-User-Id: demo-admin" -H "X-Tenant-Id: CSCEC" \
  -H "X-Role: platform_admin" -H "X-Data-Scope: tenant" \
  -d '{"project_id":"P001","accident_type":"高处坠落"}'
```

---

## 7. 文档索引

| 文档 | 用途 |
|---|---|
| `AGENTS.md` | AI 协作规范 |
| `docs/MVP_SCOPE.md` | 一期边界 |
| `docs/IMPLEMENTATION_ROADMAP.md` | Phase 0–5 任务清单 |
| `docs/PHASE5_BAYESIAN_L3_KICKOFF.md` | L3 评审纪要 |
| `docs/plans/10-bayesian-l3-implementation.md` | L3 实施 Task 清单 |
| `docs/PHASE*_ACCEPTANCE.md` | 各阶段验收报告 |

---

## 8. 维护说明

- Phase 0–4 进入**维护态**（缺陷修复、依赖安全更新）。
- **Phase 5 L3** 在 `feature/phase5-bayesian-l3` 分支按 Sprint 推进。
- 所有 Agent / 归因 / 回测输出均须人工复核（`AGENTS.md` §5.4）。

**项目状态：一期已闭环；Phase 5 L3 Sprint 1 实施中。**
