# Phase 3 启动评审议程（一页纸）

| 项 | 内容 |
|---|---|
| 会议目标 | 确认 Phase 3 范围、中间件批准、首 Sprint 与 8 周排期 |
| 建议时长 | 60–90 分钟 |
| 参会 | 产品、技术、安全（可选） |
| 材料 | `docs/PHASE2_ACCEPTANCE.md`、`docs/plans/08-phase3-four-libraries-integration.md` |

---

## 1. Phase 2 复盘（15 min）

**结论（已验收）：** Phase 2 五项门禁通过，报告见 `docs/PHASE2_ACCEPTANCE.md`。

| 门禁 | 结果 |
|---|---|
| 问数准确率 ≥85% | 105/105，`audit_pass_rate=1.0` |
| 6 Agent 可演示 | 路由 + DAG + 审批 + 三前端页 |
| 上下文命中 ≥90% | 85 用例，`context_hit_rate=1.0` |
| Prompt 回滚 | `/agent/prompts*` |
| 越权拦截 100% | data_scope + company/project |

**现场演示（任选 2 项，≤5 min）：**

1. `/agent/nl2sql` — 多轮澄清问数  
2. `/agent/hazard-advisor` — 演示模式秒级整改建议（H002/P001）  
3. `/agent/approvals` — 审批 → 人工执行  

**待签：** `PHASE2_ACCEPTANCE.md` §6 产品/技术签字栏。

---

## 2. Phase 3 范围确认（20 min）

**总目标：** 四库协同（MySQL + Redis + Milvus [+ Neo4j]）+ 认证 + 集成 + 报告。

| 子阶段 | 内容 | 默认建议 |
|:---:|---|---|
| 3-A | JWT / RBAC | 对外试点必做 |
| 3-B | Redis 业务缓存 | 可与 3-C 并行 |
| 3-C | Milvus RAG | **演示价值高，建议 Sprint 1** |
| 3-D | Neo4j 图谱 | **建议延后**（数据量小） |
| 3-E | 报告 + Webhook | Sprint 2–3 |
| 3-F | 报告页 + 移动端 | 依赖 3-A / 3-E |

**评审表决（勾选）：**

- [ ] 批准引入 **Milvus**（3-C 开工必备）
- [ ] 批准引入 **Neo4j**（可标「延后至 Phase 3 下半程」）
- [ ] 首个 Sprint：**3-C RAG** / **3-A JWT**（二选一）
- [ ] RAG 语料底线：案例 ≥20 条 + 制度片段 ≥10 条
- [ ] Embedding：**DashScope** / 本地 bge（二选一）

---

## 3. 环境与成本（15 min）

| 组件 | 现状 | Phase 3 变更 |
|---|---|---|
| MySQL | compose 已有 | 无变更 |
| Redis | compose 已有 | 3-B 增加业务缓存 |
| Milvus | 无 | compose 增加 standalone（etcd + minio） |
| Neo4j | 无 | 可选；约 +512MB 内存 |

**本地一键起（目标态）：**

```bash
docker compose -f deploy/docker-compose.yml up -d
# 评审后扩展：milvus、neo4j（可选）
```

**决策：** 开发机最低内存建议 ≥16GB（含 Milvus）。

---

## 4. 合规与 Agent 边界（10 min）

延续 `AGENTS.md`，Phase 3 不放宽：

- 向量库 / RAG **不得**入库：身份证、体检明细、人脸原图  
- Webhook / 报告中的停工、清退、处罚 → `need_human_review: true`  
- `behavior_memory` 工人行为向量 → **本期不做**  

---

## 5. 排期与首 Sprint（15 min）

**推荐 8 周排期（可调）：**

| 周 | Sprint | 交付 |
|:---:|---|---|
| W1–W2 | 3-C RAG MVP | Milvus compose + ingest + `/rag/search` + Agent evidence |
| W3–W4 | 3-A JWT | 登录 + RBAC + 前端 token |
| W5 | 3-B 缓存 | 画像/问数短缓存 |
| W6 | 3-E | 周报 API + Webhook 沙箱 |
| W7 | 3-F | 报告页 + 移动基础适配 |
| W8 | 缓冲/3-D | Neo4j 或验收收口 |

**首 Sprint 开工清单：**

1. 评审签字本议程 + `08-phase3` 计划  
2. 确认 Milvus 批准  
3. 创建分支 / worktree（可选）  
4. 执行 Task **3-C.1**（compose 加 Milvus）  

---

## 6. 会议产出（必须）

| 产出 | 负责人 | 截止日期 |
|---|---|---|
| 填妥 §2 表决勾选 | 产品+技术 | 会后 1 天 |
| 更新 `IMPLEMENTATION_ROADMAP.md` 当前 Task | 开发 | 会后 |
| Phase 3 首 Sprint Session Prompt | 开发 | 开工前 |
| `PHASE2_ACCEPTANCE.md` 签字 | 产品/技术 | 可选同步 |

---

## 7. 快速决策卡（复制到会议纪要）

```text
Phase 3 启动评审决议 — 日期：__________

1. Phase 2 验收：通过 / 有条件通过
2. Milvus：批准 / 不批准
3. Neo4j：批准 / 延后
4. 首 Sprint：3-C RAG / 3-A JWT / 其他：______
5. Embedding：DashScope / 本地
6. 目标上线日期：__________
7. 签字：产品 ______  技术 ______
```

---

**关联文档：** `docs/plans/08-phase3-four-libraries-integration.md`
