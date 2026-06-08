# 本地基础设施（Docker Compose）

## 服务一览

| 服务 | 容器名 | 宿主机端口 | 说明 |
|---|---|---|---|
| MySQL 8 | `cscec_safety_mysql` | 3306 | 主业务库 |
| Redis 7 | `cscec_safety_redis` | 6379 | 会话记忆 / 缓存 |
| etcd | `cscec_safety_etcd` | — | Milvus 元数据（仅容器网络） |
| MinIO | `cscec_safety_minio` | — | Milvus 对象存储（仅容器网络） |
| Milvus | `cscec_safety_milvus` | 29530→19530, 19091→9091 | 向量库 standalone（Phase 3-C RAG） |

## 一键启动

```bash
docker compose -f deploy/docker-compose.yml up -d
docker compose -f deploy/docker-compose.yml ps
```

Milvus 首次启动约需 60–90 秒，`healthcheck` 通过前 `milvus` 状态可能为 `starting`。

## 健康检查

```bash
# 容器级健康
docker compose -f deploy/docker-compose.yml ps

# 宿主机连通性（MySQL + Redis + Milvus）
python deploy/scripts/check_stack_health.py

# 四库应用探针 + MySQL 实连（含 Neo4j bolt，Phase 3 门禁）
cd backend
py -3.12 scripts/check_four_libraries_health.py
```

Milvus HTTP 健康端点：`http://127.0.0.1:19091/healthz`（宿主机映射，避免与 9091 冲突）  
Milvus gRPC 连接：`127.0.0.1:29530`（宿主机映射，后续 `pymilvus` / Task 3-C.2 使用）

## 环境变量（可选）

在项目根目录 `.env` 或 shell 中设置：

| 变量 | 默认 | 说明 |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `275874` | MySQL root 密码 |
| `MYSQL_DATABASE` | `cscec_safety` | 初始库名 |
| `MILVUS_ENABLED` | `false` | 启用后端 Milvus 客户端（3-C.2） |
| `MILVUS_URI` | `http://127.0.0.1:29530` | pymilvus 连接 URI |
| `MILVUS_TIMEOUT_SECONDS` | `3` | 连接超时（秒） |
| `MILVUS_ACCIDENT_CASES_COLLECTION` | `accident_cases` | 事故案例向量 collection |
| `MILVUS_EMBEDDING_DIMENSION` | `1024` | 向量维度（对齐 DashScope text-embedding-v3） |

创建 RAG collection（需 `MILVUS_ENABLED=true`）：

```bash
cd backend
MILVUS_ENABLED=true python scripts/create_milvus_collections.py
```

入库 RAG 语料（默认 `EMBEDDING_PROVIDER=disabled` 使用 mock 向量，可离线演示）：

```bash
cd backend
MILVUS_ENABLED=true EMBEDDING_PROVIDER=mock python scripts/seed_rag_corpus.py
# 生产/真实向量：EMBEDDING_PROVIDER=dashscope 且配置 DASHSCOPE_API_KEY
```

检索参数（Task 3-C.6）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `RAG_TOP_K` | `3` | 向量检索返回条数 |
| `RAG_SCORE_THRESHOLD` | `0.35` | COSINE 相似度阈值（`1 - distance`） |

RAG 检索 API（需 `agent.ask` 权限）：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/rag/search \
  -H "Content-Type: application/json" \
  -H "X-Mock-User-Id: mock-admin" -H "X-Tenant-Id: CSCEC" \
  -d "{\"query\":\"临边防护\",\"top_k\":3}"
```

宿主机端口 `29530` / `19091` 用于避免与本机已有 Milvus 或其他服务冲突；可在 `docker-compose.yml` 中按需调整映射。

## 资源建议

- 开发机内存建议 ≥16GB（Milvus standalone + MySQL + Redis）
- 仅跑 MySQL/Redis 时可选择性启动：`docker compose up -d mysql redis`

## 停止与清理

```bash
docker compose -f deploy/docker-compose.yml down
# 保留数据卷；彻底清理加 -v
```
