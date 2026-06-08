# C4 与部署视图

## 1. System Context

```text
用户/安全管理人员
  -> Vue 前端
  -> FastAPI 后端
  -> MySQL 事实库
  -> Qwen Plus（可选，安全助手）
```

平台目标是以项目、工人、分包商三类安全画像为核心，支撑风险驾驶舱、强规则预警、工单闭环和 AI 安全问答。

## 2. Container View

| 容器 | 路径 | 职责 |
|---|---|---|
| Frontend | `frontend/` | Vue 3 + Vite，展示驾驶舱、画像、工单、助手 |
| Backend API | `backend/app/` | FastAPI REST API、业务服务、统一错误响应 |
| MySQL | `intelligent_security_platform` | 主数据、隐患、设备、画像、工单、指标、Agent 审计 |
| Qwen Plus | 阿里云 DashScope | 可选 LLM 能力，无 Key 时降级 |

## 3. Component View

```text
backend/app/
  api/v1/endpoints/   HTTP 适配层
  schemas/            Pydantic 契约
  services/           业务逻辑与数据库读写
  domain/             纯业务规则
  infrastructure/     DB session、LLM client
  core/               config、responses、errors
```

分层约束：

- endpoint 不写复杂业务逻辑；
- domain 不依赖 SQLAlchemy；
- service 接收 `Session` 并负责数据库读写；
- 数据库变更必须走 Alembic。

## 4. Local Deployment

```text
PyCharm/main.py
  -> 创建/检查 .venv 依赖
  -> 检查 MySQL 3306
  -> alembic upgrade head
  -> seed_demo_data.py（幂等）
  -> uvicorn 127.0.0.1:8000
  -> vite 127.0.0.1:5173
```

默认数据库：

```text
mysql+pymysql://root:<password>@127.0.0.1:3306/intelligent_security_platform
```

`RESET_DATABASE_ON_START` 默认关闭。需要重建演示库时必须显式设置为 `1`。

## 5. P1/P2 Deployment Outlook

| 阶段 | 计划能力 |
|---|---|
| P1 | `deploy/docker-compose.full.yml`，纳入后端、前端、MySQL、Redis 预留 |
| P2 | Redis 会话记忆、Prompt 版本、Agent Checkpoint |
| P3 | Milvus（`deploy/docker-compose.yml` standalone）、Neo4j、RAG、企业微信/OA Webhook |

