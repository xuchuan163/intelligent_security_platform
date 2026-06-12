# MVP 验收标准

本文档定义中建智慧安全平台 MVP 的可验收边界。任何声称“完成”的交付都必须能用本文件中的条件验证。

## 1. 运行验收

| 项目 | 标准 | 验证方式 |
|---|---|---|
| 本地启动 | 根目录 `main.py` 可启动前后端 | PyCharm 或命令行运行 `python main.py` |
| 后端地址 | FastAPI 监听 `127.0.0.1:8000` | 访问 `/api/v1/health` |
| 前端地址 | Vite 监听 `127.0.0.1:5173` | 浏览器访问首页 |
| 数据库 | MySQL `intelligent_security_platform` 可迁移和 seed | `alembic upgrade head` + `seed_demo_data.py` |

## 2. 功能验收

| 模块 | MVP 验收条件 |
|---|---|
| 驾驶舱 | 展示项目总数、高风险项目、工单状态和项目风险排名 |
| 项目画像 | 可查询项目画像、项目风险排名、触发项目画像重算 |
| 工人画像 | 可查询工人风险画像，返回风险等级、标签和解释 |
| 分包商画像 | 可查询分包商风险画像，返回风险等级和关键比例 |
| 强规则日志 | `/api/v1/rules/triggers` 返回最近规则触发记录 |
| 工单 | 支持列表、创建、状态流转，非法流转返回 409 |
| 指标目录 | `/api/v1/metrics/catalog` 和 `/api/v1/metrics/{metric_code}` 可查 |
| 事故案例库 | `/api/v1/case/list` 返回不少于 5 条结构化案例，且按租户过滤 |
| AI 助手 | 无 Key 时降级可用，有 Key 时调用 Qwen，输出需人工复核 |

## 3. 数据验收

| 对象 | 当前演示数据 |
|---|---:|
| 租户 | 1 |
| 项目 | 3 |
| 分包商 | 3 |
| 工人 | 8 |
| 隐患 | 7 |
| 设备 | 4 |
| 工单 | 5 |
| 指标 | 32 |
| 事故案例 | 5 |

## 4. 接口验收

所有成功业务接口必须返回：

```json
{"code": "SUCCESS", "message": "ok", "data": {}}
```

错误接口必须返回：

```json
{
  "code": "40401",
  "message": "Not Found",
  "request_id": "uuid",
  "data": null,
  "timestamp": "2026-06-03T10:00:00+08:00"
}
```

## 5. 质量验收

| 项目 | 标准 |
|---|---|
| 后端测试 | `pytest -v` 全部通过 |
| 前端构建 | `npm run build` 通过 |
| 数据库结构 | `python scripts/check_db_schema.py` 通过 |
| OpenAPI | `docs/api/openapi.yaml` 与当前 FastAPI 路由一致 |
| 安全 | 不提交真实 `.env`、API Key、身份证号、体检明细、人脸原图 |

## 6. Phase 1 出口结论

截至 2026-06-04，Phase 1 出口门禁为：

- 后端 `pytest -v` 全绿；
- 前端 `npm run build` 通过；
- `python scripts/check_db_schema.py` 通过；
- `docs/api/openapi.yaml` 已按当前 FastAPI 路由重新生成；
- MVP_SCOPE 内 Phase 1 必做项已闭合，Phase 2 可进入启动评审。

## 7. Phase 2 出口结论

截至 2026-06-03，Phase 2 里程碑验收见 **`docs/PHASE2_ACCEPTANCE.md`**：

- 问数准确率、六 Agent 编排、权限越权拦截：**通过**（85 项门禁 pytest 全绿）；
- 会话上下文命中率：**通过**（85 用例基准，`context_hit_rate=1.0`）；Prompt 回滚：**通过**（`/agent/prompts*`）；
- Agent/NL2SQL 已支持 `session_id` 多轮记忆接入；Docker Compose 已含 Redis 服务。
- 演示入口：`/agent/nl2sql`、`/agent/hazard-advisor`（默认演示模式）、`/agent/approvals`、`/analysis/attribution`。

## 8. Phase 3 里程碑验收

截至 2026-06-03，Phase 3 里程碑验收见 **`docs/PHASE3_ACCEPTANCE.md`**：

- RAG top-3 命中率、四库健康、JWT/RBAC、Webhook、报告 API、全量 pytest + schema + 前端 build：**通过**。

## 9. Phase 4 入口门禁（评审后生效）

开工前须完成 **`docs/PHASE4_KICKOFF_AGENDA.md`** 表决；编码按 **`docs/plans/09-phase4-algorithm-and-scale.md`** 子阶段推进。

| # | 表决项 | 默认建议 |
|:---:|---|---|
| 1 | 首 Sprint | 4-A 权重 + 4-B 案例 ≥50 |
| 2 | 贝叶斯 L2 | 案例达 50 条后再批准 |
| 3 | 贝叶斯 L3 | **已通过**（案例≥200 + `PHASE5_BAYESIAN_L3_ACCEPTANCE.md`） |
| 4 | behavior_memory | 本期不做（需合规签字） |
| 5 | 压测目标 | 500 项目门禁 / 2000 项目 stretch |

| # | 里程碑 | 目标 | 验证方式 |
|:---:|---|---|---|
| 1 | RAG 检索 | top-3 命中率 ≥ 80% | `tests/datasets/rag_retrieval_30.jsonl` + benchmark |
| 2 | 三/四库就绪 | MySQL + Redis + Milvus compose 健康 | `docker compose up` + `/health` |
| 3 | 认证 | JWT 登录闭环，RBAC 越权拦截 100% | `test_auth_jwt` + `test_rbac` |
| 4 | Webhook | 沙箱投递成功并写审计日志 | `webhook_delivery_log` + 手动触发 |
| 5 | 报告 | 项目周报 API 可 curl 演示 | `GET /reports/project-weekly/{id}` + 前端页 |
| 6 | 质量 | pytest 全绿、schema check、`npm run build` | 与 Phase 1/2 同级 |

**中间件批准（AGENTS.md 强制）：**

- Milvus：3-C 开工前必须明确批准
- Neo4j：3-D 开工前必须明确批准（默认建议延后）
