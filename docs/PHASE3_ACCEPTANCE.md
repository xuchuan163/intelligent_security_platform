# Phase 3 里程碑验收报告

**验收日期：** 2026-06-03  
**验收范围：** `docs/plans/08-phase3-four-libraries-integration.md` §9 六项门禁  
**验证环境：** Python 3.12.10、Windows 11、本机 MySQL:3306 + Redis:6379 + Milvus（cscec compose 映射 19091/29530）+ Neo4j:7687

---

## 1. 总览

| # | 里程碑 | 目标 | 结论 | 证据摘要 |
|:---:|---|---|---|---|
| 1 | RAG 检索 | top-3 命中率 ≥ 80% | **通过** | `rag_retrieval_30.jsonl` 30/30；`top_k_hit_rate=1.0` |
| 2 | 四库就绪 | MySQL + Redis + Milvus（+ Neo4j 可选）健康 | **通过** | `check_stack_health.py` 全绿；`check_four_libraries_health.py` 全绿 |
| 3 | 认证 | JWT 登录 + RBAC 越权拦截 100% | **通过** | `test_auth_jwt*` + `test_rbac*` 31 项门禁子集全绿 |
| 4 | 集成 | Webhook 沙箱投递 + 审计日志 | **通过** | `test_webhook_*` 全绿；`POST /webhooks/test` 已挂载 |
| 5 | 报告 | 项目周报 / 分包商评价 API + 前端页 | **通过** | `test_reports_api`；路由 `/reports/project`、`/reports/subcontractor` |
| 6 | 质量 | pytest 全绿 + schema check + `npm run build` | **通过** | **337 passed**；29 张 ORM 表对齐；前端 build 成功 |

**Phase 3 里程碑结论：通过** — 六项门禁均已达标（含四库健康一键检查脚本与全量 pytest）。

---

## 2. 自动化验证

### 2.1 四库健康（一键）

```bash
# 宿主机 TCP / HTTP（compose 映射端口）
python deploy/scripts/check_stack_health.py

# 应用侧探针 + MySQL SELECT 1（含 Neo4j bolt 可选）
cd backend
py -3.12 scripts/check_four_libraries_health.py
py -3.12 scripts/check_db_schema.py
```

**2026-06-03 实测：**

| 检查项 | 结果 |
|---|---|
| `mysql` (3306 TCP + ORM 连接) | ok |
| `redis` (6379 + `probe_redis_status`) | ready |
| `milvus` (19091/healthz + 29530 gRPC) | stack ok（`MILVUS_ENABLED=false` 时探针为 disabled，栈连通即验收） |
| `neo4j` (7687 bolt TCP) | ok（`NEO4J_ENABLED=false` 时探针为 disabled，实例已运行） |
| `four_libraries` 汇总 | **ok** |
| Schema（29 ORM 表） | **passed** |

**环境说明：**

- 本机 3306 已被宿主机 MySQL 占用，`cscec_safety_mysql` 容器未能绑定端口；业务库 `intelligent_security_platform` 使用宿主机实例。
- 验收前已执行 Alembic 升级至 `20260610_0015`（补全 `user_role`、`auth_role`、`webhook_delivery_log` 等 Phase 3 表）。
- Milvus 容器 `cscec_safety_milvus` 需 `docker start` 后 health 才可达（etcd/minio 依赖已 healthy）。

### 2.2 全量 pytest

```bash
cd backend
py -3.12 -m pytest -v
```

**结果：** `337 passed`（2026-06-03，46.54s）

**门禁子集（认证 / RAG / Webhook）：**

```bash
py -3.12 -m pytest \
  tests/services/test_auth_jwt_tokens.py \
  tests/api/test_auth_jwt_api.py \
  tests/services/test_rbac_permissions.py \
  tests/api/test_rbac_api.py \
  tests/services/test_rag_retrieve_benchmark.py \
  tests/services/test_webhook_test_delivery.py \
  tests/services/test_webhook_delivery_log.py \
  -q
```

**结果：** `31 passed`

### 2.3 RAG Benchmark

```bash
cd backend
py -3.12 scripts/run_rag_benchmark.py
```

```json
{
  "total": 30,
  "passed": 30,
  "top_k_hit_rate": 1.0
}
```

### 2.4 前端构建

```bash
cd frontend
npm run build
```

**结果：** `vue-tsc -b && vite build` 成功（~11s）

---

## 3. 验收前修复项（本次会话）

| 问题 | 处理 |
|---|---|
| 缺表 `user_role` 等导致 smoke/RBAC 失败 | `alembic upgrade head`（0013–0015） |
| `test_get_current_user_reads_subcontractor_header` 直接调用依赖函数 | 显式传入 `credentials=None` |
| NL2SQL API 测试被 Redis 缓存污染 | `dependency_overrides[get_redis_client_optional] = lambda: None` |
| Windows `pytest` 临时目录 PermissionError | `pyproject.toml` 增加 `addopts = "--basetemp=.pytest_tmp"` |
| 缺四库一键脚本 | 新增 `backend/scripts/check_four_libraries_health.py` |

---

## 4. API 健康端点（参考）

`GET /api/v1/health` 返回 `redis`、`milvus`、`neo4j` 探针；Redis 不可用时整体 `degraded`。

启用 Milvus/Neo4j 客户端探针时，在 `backend/.env` 设置：

```env
MILVUS_ENABLED=true
MILVUS_URI=http://127.0.0.1:29530
NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
```

---

## 5. 关联文档

- 实施计划：`docs/plans/08-phase3-four-libraries-integration.md`
- 路线图：`docs/IMPLEMENTATION_ROADMAP.md` Phase 3 里程碑
- 基础设施：`deploy/README.md`
