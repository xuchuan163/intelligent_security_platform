# Smart Safety Platform MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable full-stack MVP for the CSCEC smart construction safety platform with MySQL-backed risk profiles, strong-rule warnings, work orders, dashboard UI, and a Qwen-powered safety assistant.

**Architecture:** Use a monorepo with a FastAPI backend and Vue 3 frontend. Keep domain calculations framework-independent, persist facts and profile results in MySQL, and treat Qwen as an explain/suggest/report helper that cannot override strong-rule conclusions.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, PyMySQL, pytest, Vue 3, Vite, TypeScript, ECharts, Axios, Docker Compose, MySQL 8.

---

## File Structure

Create these top-level areas:

- `backend/`: FastAPI app, migrations, scripts, and backend tests.
- `frontend/`: Vue 3 app with dashboard, profile, work-order, and assistant pages.
- `deploy/`: Docker Compose for local MySQL.
- `docs/superpowers/specs/`: approved design spec.
- `docs/superpowers/plans/`: this implementation plan.
- `.gitignore`, `.env.example`, `README.md`: shared project setup files.

Backend responsibility map:

- `backend/app/core/`: settings, response helpers, logging-safe configuration.
- `backend/app/domain/`: enums, pure risk calculation, work-order state machine.
- `backend/app/infrastructure/database/`: SQLAlchemy engine, session, ORM models.
- `backend/app/infrastructure/llm/`: Qwen OpenAI-compatible client wrapper.
- `backend/app/services/`: profile calculation, rules, work orders, assistant orchestration.
- `backend/app/api/v1/endpoints/`: HTTP routes only.
- `backend/tests/`: pytest coverage for domain, services, and API smoke tests.

Frontend responsibility map:

- `frontend/src/api/`: typed Axios client.
- `frontend/src/types/`: shared response and domain types.
- `frontend/src/pages/`: dashboard, profiles, work orders, assistant.
- `frontend/src/components/`: charts, stat blocks, risk tags, status chips.
- `frontend/src/router/`: routes.

---

## Task 1: Shared Project Skeleton

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `deploy/docker-compose.yml`

- [ ] **Step 1: Create ignore and environment template**

Write `.gitignore`:

```gitignore
.env
.venv/
__pycache__/
.pytest_cache/
*.pyc
node_modules/
dist/
.superpowers/
backend/.coverage
backend/htmlcov/
frontend/.vite/
```

Write `.env.example`:

```text
APP_ENV=local
DATABASE_URL=mysql+pymysql://root:password@localhost:3306/cscec_safety
DASHSCOPE_API_KEY=replace-me
QWEN_MODEL=qwen-plus
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

- [ ] **Step 2: Create Docker Compose for MySQL**

Write `deploy/docker-compose.yml`:

```yaml
services:
  mysql:
    image: mysql:8.0
    container_name: cscec_safety_mysql
    environment:
      MYSQL_ROOT_PASSWORD: ${MYSQL_ROOT_PASSWORD:-275874}
      MYSQL_DATABASE: ${MYSQL_DATABASE:-cscec_safety}
    ports:
      - "3306:3306"
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci
    volumes:
      - mysql_data:/var/lib/mysql

volumes:
  mysql_data:
```

- [ ] **Step 3: Create root README**

Write `README.md` with:

```markdown
# 中建智慧安全平台 MVP

本工程是一期全栈 MVP：FastAPI 后端、Vue3 前端、MySQL 主库、三类风险画像、强规则预警、工单闭环和 Qwen 安全助手。

## 安全提醒

`.env` 不提交。阿里云 Key 和数据库密码从环境变量读取；生产环境不要使用 root 数据库账号。

## 本地启动

1. `copy .env.example .env`
2. 在 `.env` 中填写 `DATABASE_URL` 和 `DASHSCOPE_API_KEY`
3. `docker compose -f deploy/docker-compose.yml up -d`
4. 后端：进入 `backend` 后安装依赖、执行迁移、导入示例数据并启动 FastAPI
5. 前端：进入 `frontend` 后安装依赖并启动 Vite
```

- [ ] **Step 4: Verify skeleton files**

Run:

```powershell
Get-ChildItem -Force
```

Expected: `.gitignore`, `.env.example`, `README.md`, `deploy/` are present.

---

## Task 2: Backend Scaffolding and Settings

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/main.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/core/responses.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write failing health API test**

Create `backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint_returns_success():
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "code": "SUCCESS",
        "message": "ok",
        "data": {"status": "healthy"},
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend
python -m pytest tests/test_health.py -v
```

Expected: FAIL because `app.main` does not exist.

- [ ] **Step 3: Implement minimal backend scaffold**

Create `backend/pyproject.toml`:

```toml
[project]
name = "cscec-smart-safety-backend"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "sqlalchemy>=2.0.0",
  "alembic>=1.13.0",
  "pymysql>=1.1.0",
  "pydantic-settings>=2.4.0",
  "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[tool.pytest.ini_options]
pythonpath = ["."]
```

Create `backend/app/core/responses.py`:

```python
from typing import Any


def success(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": "SUCCESS", "message": message, "data": data}
```

Create `backend/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    database_url: str = "mysql+pymysql://root:password@localhost:3306/cscec_safety"
    dashscope_api_key: str | None = None
    qwen_model: str = "qwen-plus"
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8")


settings = Settings()
```

Create `backend/app/main.py`:

```python
from fastapi import FastAPI

from app.core.responses import success

app = FastAPI(title="中建智慧安全平台 MVP", version="0.1.0")


@app.get("/api/v1/health")
def health() -> dict:
    return success({"status": "healthy"})
```

- [ ] **Step 4: Run health test to verify it passes**

Run:

```powershell
cd backend
python -m pytest tests/test_health.py -v
```

Expected: PASS.

---

## Task 3: Domain Risk Calculation

**Files:**
- Create: `backend/app/domain/risk.py`
- Create: `backend/tests/domain/test_risk.py`

- [ ] **Step 1: Write failing risk tests**

Create `backend/tests/domain/test_risk.py`:

```python
from app.domain.risk import RiskLevel, calculate_final_score, level_for_score


def test_calculate_final_score_caps_at_100():
    score = calculate_final_score(base_score=80, dynamic_factor=1.5, rule_bonus=30)

    assert score == 100


def test_level_for_score_uses_documented_thresholds():
    assert level_for_score(20) == RiskLevel.LOW
    assert level_for_score(45) == RiskLevel.MEDIUM
    assert level_for_score(72) == RiskLevel.HIGH
    assert level_for_score(90) == RiskLevel.CRITICAL
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/domain/test_risk.py -v
```

Expected: FAIL because `app.domain.risk` does not exist.

- [ ] **Step 3: Implement pure risk domain logic**

Create `backend/app/domain/risk.py`:

```python
from enum import StrEnum


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def calculate_final_score(base_score: float, dynamic_factor: float, rule_bonus: float) -> float:
    raw_score = base_score * dynamic_factor + rule_bonus
    return round(min(100, max(0, raw_score)), 2)


def level_for_score(score: float) -> RiskLevel:
    if score <= 30:
        return RiskLevel.LOW
    if score <= 60:
        return RiskLevel.MEDIUM
    if score <= 80:
        return RiskLevel.HIGH
    return RiskLevel.CRITICAL
```

- [ ] **Step 4: Verify risk tests pass**

Run:

```powershell
cd backend
python -m pytest tests/domain/test_risk.py -v
```

Expected: PASS.

---

## Task 4: Work Order State Machine

**Files:**
- Create: `backend/app/domain/work_orders.py`
- Create: `backend/tests/domain/test_work_orders.py`

- [ ] **Step 1: Write failing work-order tests**

Create `backend/tests/domain/test_work_orders.py`:

```python
import pytest

from app.domain.work_orders import WorkOrderStatus, transition_status


def test_work_order_can_move_from_pending_to_dispatched():
    assert transition_status(WorkOrderStatus.PENDING_CONFIRM, "confirm") == WorkOrderStatus.DISPATCHED


def test_invalid_work_order_transition_is_rejected():
    with pytest.raises(ValueError, match="Invalid work-order transition"):
        transition_status(WorkOrderStatus.CLOSED, "accept")
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/domain/test_work_orders.py -v
```

Expected: FAIL because `app.domain.work_orders` does not exist.

- [ ] **Step 3: Implement state machine**

Create `backend/app/domain/work_orders.py`:

```python
from enum import StrEnum


class WorkOrderStatus(StrEnum):
    PENDING_CONFIRM = "pending_confirm"
    DISPATCHED = "dispatched"
    PROCESSING = "processing"
    WAITING_REVIEW = "waiting_review"
    CLOSED = "closed"
    REJECTED = "rejected"
    OVERDUE_ESCALATED = "overdue_escalated"


_TRANSITIONS = {
    (WorkOrderStatus.PENDING_CONFIRM, "confirm"): WorkOrderStatus.DISPATCHED,
    (WorkOrderStatus.DISPATCHED, "accept"): WorkOrderStatus.PROCESSING,
    (WorkOrderStatus.PROCESSING, "submit_result"): WorkOrderStatus.WAITING_REVIEW,
    (WorkOrderStatus.WAITING_REVIEW, "review_pass"): WorkOrderStatus.CLOSED,
    (WorkOrderStatus.WAITING_REVIEW, "review_reject"): WorkOrderStatus.PROCESSING,
    (WorkOrderStatus.PROCESSING, "timeout"): WorkOrderStatus.OVERDUE_ESCALATED,
}


def transition_status(current: WorkOrderStatus, action: str) -> WorkOrderStatus:
    next_status = _TRANSITIONS.get((current, action))
    if next_status is None:
        raise ValueError(f"Invalid work-order transition: {current} + {action}")
    return next_status
```

- [ ] **Step 4: Verify work-order tests pass**

Run:

```powershell
cd backend
python -m pytest tests/domain/test_work_orders.py -v
```

Expected: PASS.

---

## Task 5: Database Models, Alembic, and Seed Data

**Files:**
- Create: `backend/app/infrastructure/database/session.py`
- Create: `backend/app/infrastructure/database/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/20260602_0001_initial_schema.py`
- Create: `backend/scripts/seed_demo_data.py`
- Create: `backend/tests/services/test_profile_service.py`

- [ ] **Step 1: Write failing profile service test**

Create `backend/tests/services/test_profile_service.py`:

```python
from app.services.profiles.calculator import calculate_project_profile


def test_project_profile_includes_rule_bonus_and_level():
    result = calculate_project_profile(
        hazard_overdue_count=1,
        major_hazard_overdue_count=1,
        equipment_overdue_count=0,
        schedule_pressure_index=10,
    )

    assert result.total_risk_score >= 61
    assert result.risk_level == "high"
    assert "重大隐患超期未闭环" in result.risk_tags
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/services/test_profile_service.py -v
```

Expected: FAIL because profile calculator does not exist.

- [ ] **Step 3: Implement database models**

Create SQLAlchemy models for `Tenant`, `Project`, `Subcontractor`, `Worker`, `Hazard`, `Equipment`, `ProjectRiskProfile`, `WorkerRiskProfile`, `SubcontractorRiskProfile`, `RuleTriggerLog`, `SafetyWorkOrder`, and `AgentTaskLog`. Include `tenant_id`, timestamps, and JSON fields for tags/evidence.

- [ ] **Step 4: Implement Alembic migration**

Create the initial migration with tables matching the models. Use MySQL `JSON` for tags/evidence and `String(64)` IDs for business keys.

- [ ] **Step 5: Implement profile calculator**

Create `backend/app/services/profiles/calculator.py` with:

```python
from dataclasses import dataclass

from app.domain.risk import calculate_final_score, level_for_score


@dataclass(frozen=True)
class ProfileResult:
    total_risk_score: float
    risk_level: str
    risk_tags: list[str]
    evidence: list[str]
    data_completeness: float
    human_review_required: bool


def calculate_project_profile(
    hazard_overdue_count: int,
    major_hazard_overdue_count: int,
    equipment_overdue_count: int,
    schedule_pressure_index: float,
) -> ProfileResult:
    base_score = min(60, hazard_overdue_count * 8 + equipment_overdue_count * 10 + schedule_pressure_index)
    rule_bonus = 0
    tags: list[str] = []
    evidence: list[str] = []

    if major_hazard_overdue_count > 0:
        rule_bonus += 20
        tags.append("重大隐患超期未闭环")
        evidence.append("rule:SR-PROJ-001")
    if equipment_overdue_count > 0:
        rule_bonus += 25
        tags.append("特种设备超期未检")
        evidence.append("rule:SR-PROJ-004")

    score = calculate_final_score(base_score, 1.0, rule_bonus)
    level = level_for_score(score).value
    if rule_bonus >= 20 and level in {"low", "medium"}:
        level = "high"
        score = max(score, 61)

    return ProfileResult(
        total_risk_score=score,
        risk_level=level,
        risk_tags=tags,
        evidence=evidence,
        data_completeness=0.85,
        human_review_required=rule_bonus > 0,
    )
```

- [ ] **Step 6: Verify profile service test passes**

Run:

```powershell
cd backend
python -m pytest tests/services/test_profile_service.py -v
```

Expected: PASS.

- [ ] **Step 7: Add seed script**

Create `backend/scripts/seed_demo_data.py` that inserts:

- one tenant
- three projects
- three subcontractors
- eight workers
- hazards with mixed severities and statuses
- equipment with one overdue inspection
- initial profile rows and one rule trigger log

- [ ] **Step 8: Verify migration and seed manually**

Run:

```powershell
docker compose -f deploy/docker-compose.yml up -d
cd backend
alembic upgrade head
python scripts/seed_demo_data.py
```

Expected: tables exist and script reports inserted demo data.

---

## Task 6: Backend Services and API Routes

**Files:**
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/schemas/profiles.py`
- Create: `backend/app/schemas/work_orders.py`
- Create: `backend/app/services/dashboard.py`
- Create: `backend/app/services/profiles/service.py`
- Create: `backend/app/services/work_orders/service.py`
- Create: `backend/app/api/v1/router.py`
- Create: `backend/app/api/v1/endpoints/dashboard.py`
- Create: `backend/app/api/v1/endpoints/profiles.py`
- Create: `backend/app/api/v1/endpoints/work_orders.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_api_smoke.py`

- [ ] **Step 1: Write failing API smoke tests**

Create `backend/tests/test_api_smoke.py`:

```python
from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_overview_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/dashboard/overview")

    assert response.status_code in {200, 503}


def test_work_orders_route_exists():
    client = TestClient(app)

    response = client.get("/api/v1/work-orders")

    assert response.status_code in {200, 503}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/test_api_smoke.py -v
```

Expected: FAIL or 404 because routes do not exist.

- [ ] **Step 3: Implement schemas, services, and routes**

Implement routes:

- `GET /api/v1/dashboard/overview`
- `GET /api/v1/profile/project/{project_id}`
- `GET /api/v1/profile/worker/{worker_id}`
- `GET /api/v1/profile/subcontractor/{subcontractor_id}`
- `GET /api/v1/profile/ranking/projects`
- `POST /api/v1/profile/recalculate`
- `GET /api/v1/rules/triggers`
- `GET /api/v1/work-orders`
- `POST /api/v1/work-orders`
- `PATCH /api/v1/work-orders/{work_order_id}/status`

If the database is unavailable, return HTTP 503 with a clear message rather than crashing.

- [ ] **Step 4: Verify API smoke tests pass**

Run:

```powershell
cd backend
python -m pytest tests/test_api_smoke.py -v
```

Expected: PASS.

---

## Task 7: Qwen Safety Assistant

**Files:**
- Create: `backend/app/infrastructure/llm/qwen_client.py`
- Create: `backend/app/services/agents/safety_assistant.py`
- Create: `backend/app/schemas/assistant.py`
- Create: `backend/app/api/v1/endpoints/assistant.py`
- Modify: `backend/app/api/v1/router.py`
- Create: `backend/tests/services/test_safety_assistant.py`

- [ ] **Step 1: Write failing assistant tests**

Create `backend/tests/services/test_safety_assistant.py`:

```python
from app.services.agents.safety_assistant import SafetyAssistantService


def test_assistant_returns_clear_error_when_key_missing():
    service = SafetyAssistantService(api_key=None)

    result = service.chat("解释 A 项目风险", context={})

    assert result["available"] is False
    assert "DASHSCOPE_API_KEY" in result["message"]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
cd backend
python -m pytest tests/services/test_safety_assistant.py -v
```

Expected: FAIL because assistant service does not exist.

- [ ] **Step 3: Implement Qwen client and assistant service**

Implement an OpenAI-compatible HTTP call to:

```text
POST {QWEN_BASE_URL}/chat/completions
```

Use headers:

```text
Authorization: Bearer {DASHSCOPE_API_KEY}
Content-Type: application/json
```

System prompt must include:

```text
你是施工安全智能平台助手。你只能基于已提供的结构化事实、规则命中和证据摘要进行解释。
强规则和数据库事实优先于自然语言推理。
涉及停工、限制作业、处罚、清退等动作时，只能输出建议，必须提示人工复核。
不要输出身份证、手机号、健康明细等敏感信息。
```

- [ ] **Step 4: Add assistant endpoints**

Implement:

- `POST /api/v1/assistant/chat`
- `POST /api/v1/assistant/project-risk-explanation`

- [ ] **Step 5: Verify assistant tests pass**

Run:

```powershell
cd backend
python -m pytest tests/services/test_safety_assistant.py -v
```

Expected: PASS.

---

## Task 8: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.ts`
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/types/api.ts`

- [ ] **Step 1: Create Vue/Vite scaffold**

Create `frontend/package.json`:

```json
{
  "scripts": {
    "dev": "vite --host 127.0.0.1",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview --host 127.0.0.1"
  },
  "dependencies": {
    "@vitejs/plugin-vue": "^5.2.0",
    "axios": "^1.7.0",
    "echarts": "^5.5.0",
    "lucide-vue-next": "^0.468.0",
    "vue": "^3.5.0",
    "vue-router": "^4.4.0"
  },
  "devDependencies": {
    "typescript": "^5.6.0",
    "vite": "^6.0.0",
    "vue-tsc": "^2.1.0"
  }
}
```

- [ ] **Step 2: Implement shell layout and typed API client**

Use a quiet operational layout: left navigation, top status strip, main work area. Do not create a marketing landing page.

- [ ] **Step 3: Verify frontend scaffold builds**

Run:

```powershell
cd frontend
npm install
npm run build
```

Expected: build succeeds.

---

## Task 9: Frontend Pages and Components

**Files:**
- Create: `frontend/src/components/RiskBadge.vue`
- Create: `frontend/src/components/StatTile.vue`
- Create: `frontend/src/components/ProjectRiskChart.vue`
- Create: `frontend/src/pages/DashboardPage.vue`
- Create: `frontend/src/pages/ProjectProfilePage.vue`
- Create: `frontend/src/pages/WorkerProfilePage.vue`
- Create: `frontend/src/pages/SubcontractorProfilePage.vue`
- Create: `frontend/src/pages/WorkOrdersPage.vue`
- Create: `frontend/src/pages/AssistantPage.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Implement operational dashboard**

Dashboard must show:

- total projects
- high-risk projects
- open work orders
- overdue work orders
- project risk ranking chart
- work-order status list

- [ ] **Step 2: Implement profile pages**

Profile pages must show:

- risk score
- risk level
- tags
- evidence
- human review hint

- [ ] **Step 3: Implement work-order board**

Work-order page must show table rows with:

- order ID
- type
- project
- status
- due date
- risk source

- [ ] **Step 4: Implement assistant page**

Assistant page must call `POST /api/v1/assistant/chat` and display:

- assistant response
- availability/error message
- facts-first warning text from backend when key is missing

- [ ] **Step 5: Verify frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds with no TypeScript errors.

---

## Task 10: End-to-End Verification and Startup

**Files:**
- Modify: `README.md`
- Optional Create: `backend/scripts/dev_check.py`

- [ ] **Step 1: Run backend test suite**

Run:

```powershell
cd backend
python -m pytest -v
```

Expected: all backend tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds.

- [ ] **Step 3: Start services**

Run:

```powershell
docker compose -f deploy/docker-compose.yml up -d
cd backend
alembic upgrade head
python scripts/seed_demo_data.py
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another shell:

```powershell
cd frontend
npm run dev
```

Expected:

- Backend at `http://127.0.0.1:8000`
- Swagger at `http://127.0.0.1:8000/docs`
- Frontend at Vite URL, normally `http://127.0.0.1:5173`

- [ ] **Step 4: Manual smoke check**

Open frontend and confirm:

- dashboard loads without blank screen
- project ranking chart renders
- profile pages show risk tags
- work-order list shows demo rows
- assistant page returns Qwen response if key is configured, otherwise returns a clear missing-key message

- [ ] **Step 5: Update README with final commands**

Add exact verified commands and known limitations:

- Neo4j, Milvus, Redis, NL2SQL, and full multi-Agent DAG are reserved for later phases.
- Qwen cannot override strong-rule conclusions.
- `.env` must not be committed.

---

## Plan Self-Review

Spec coverage:

- Three profile types: Tasks 3, 5, 6, 9.
- Strong rules: Tasks 3, 5, 6, 9.
- Work-order closed loop: Tasks 4, 6, 9.
- Qwen assistant: Task 7 and Task 9.
- MySQL and seed data: Task 5 and Task 10.
- Frontend dashboard and pages: Tasks 8 and 9.
- Verification: Task 10.

Placeholder scan:

- No `TBD`, `TODO`, or undefined implementation handoffs are intentionally left in the plan.

Type consistency:

- `RiskLevel`, `WorkOrderStatus`, `ProfileResult`, and API paths are used consistently across tasks.
