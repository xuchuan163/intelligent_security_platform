# 07 Phase 2 Agent & Memory Plan（概要）

## 当前启动结论（2026-06-04）

- 用户已批准 Phase 2 引入 Redis，本地端口 `6379`，可通过 Redis Insight 连接。
- 第一段只执行记忆系统 `2.1.x`，暂不进入 NL2SQL 和 6 Agent DAG。
- Redis 会话 TTL 固定为 1800 秒。
- MySQL 仅归档会话摘要，不保存完整 SQL 结果。
- Milvus、Neo4j、完整 RAG、生产级认证继续后置。

> **门禁：** Phase 1 里程碑全部勾选 + 用户明确批准引入 Redis。

## 2.1 记忆系统

| Task | 交付 |
|:---:|---|
| 2.1.1 | `deploy/docker-compose.full.yml` 增加 Redis 7 |
| 2.1.2 | `session:{user_id}:{session_id}` TTL 1800，`store_full_sql_result: false` |
| 2.1.3 | `agent_session_summary` MySQL 归档 |
| 2.1.4 | `agent_task_checkpoint` 表 + Redis 热状态 |
| 2.1.5 | `GET/POST /api/v1/memory/session` |

## 2.2–2.5

见 `docs/IMPLEMENTATION_ROADMAP.md` Phase 2 表格；每块开工前复制 `VIBE_CODING_PLAYBOOK.md` Session Prompt。

## 禁止提前做

- NL2SQL 全量、6 Agent DAG、Milvus、Neo4j（均属 Phase 2–3 边界）
