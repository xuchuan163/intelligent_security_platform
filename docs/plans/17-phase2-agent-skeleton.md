# Phase 2 Agent Prompt Version And Skeleton Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish six Agent prompt identities, prompt version registration, and a route-only `/api/v1/agent/ask` boundary without implementing multi-Agent orchestration.

**Architecture:** Prompt files live under `prompts/agents/` and are registered into `agent_prompt_version`. Backend services load prompt metadata, resolve the active version, and route a user message to one target agent using deterministic keyword rules. The endpoint returns a route preview only; no tools, DAG, SQL, or downstream Agent execution is triggered.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest, local Markdown prompt files.

---

## Task 1: RED Tests

**Files:**
- Create: `backend/tests/services/test_agent_prompt_versions.py`
- Create: `backend/tests/services/test_agent_router.py`
- Create: `backend/tests/api/test_agent_ask_api.py`

- [x] Write tests that expect `AgentPromptVersion`, prompt sync service, route service, and `/api/v1/agent/ask`.
- [x] Run targeted tests and confirm RED due to missing model/service/API.

Command:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests\services\test_agent_prompt_versions.py tests\services\test_agent_router.py tests\api\test_agent_ask_api.py -q
```

## Task 2: Model And Migration

**Files:**
- Modify: `backend/app/infrastructure/database/models.py`
- Create: `backend/alembic/versions/20260605_0009_agent_prompt_version.py`
- Modify: `backend/scripts/check_db_schema.py` only if needed

- [x] Add `AgentPromptVersion` ORM model.
- [x] Add idempotent Alembic migration.
- [x] Ensure schema check expects 21 ORM tables after migration.

## Task 3: Prompt Files And Seed Service

**Files:**
- Create: `prompts/agents/safety_supervisor.md`
- Create: `prompts/agents/risk_profile_analyst.md`
- Create: `prompts/agents/rule_compliance_checker.md`
- Create: `prompts/agents/work_order_coordinator.md`
- Create: `prompts/agents/nl2sql_analyst.md`
- Create: `prompts/agents/hazard_rectification_advisor.md`
- Create: `backend/app/services/agents/prompt_registry.py`
- Modify: `backend/scripts/seed_demo_data.py`

- [x] Create six prompt files with role, input, output JSON, evidence, and safety boundary sections.
- [x] Implement `sync_agent_prompt_versions(db)`.
- [x] Implement `list_active_prompt_versions(db)` and `get_active_prompt_version(db, agent_code)`.
- [x] Call sync from `seed_demo_data.py`.

## Task 4: Route-Only Agent Ask Service

**Files:**
- Create: `backend/app/schemas/agent.py`
- Create: `backend/app/services/agents/router.py`
- Modify: `backend/app/api/v1/endpoints/agent.py`

- [x] Add `AgentAskRequest` and route-preview response schema.
- [x] Implement deterministic intent rules for six agents.
- [x] Force `need_human_review=true` for stop-work, penalty, removal, or disciplinary language.
- [x] Add `POST /api/v1/agent/ask`.
- [x] Ensure `/agent/ask` never calls NL2SQL execution or other downstream tools.

## Task 5: Docs And Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_ROADMAP.md`
- Modify: `README.md`
- Modify: `docs/plans/17-phase2-agent-skeleton.md`

- [x] Record 2.4-A delivery status.
- [x] Add README note for route-only `/agent/ask`.
- [x] Run targeted tests.
- [x] Run schema check.
- [x] Run full backend pytest.

Commands:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests\services\test_agent_prompt_versions.py tests\services\test_agent_router.py tests\api\test_agent_ask_api.py -q
..\.venv\Scripts\python.exe scripts\check_db_schema.py
..\.venv\Scripts\python.exe -m pytest -q
```

## Acceptance

- Six prompt files exist and include evidence/human-review boundaries.
- `agent_prompt_version` exists and seed sync registers six active prompt versions.
- `/api/v1/agent/ask` returns `execution_mode="route_only"`.
- Each representative intent routes to the expected target agent.
- Stop-work/penalty/removal language requires human review.
- No DAG orchestration or downstream tool execution is introduced.
- Full backend tests pass.

## Delivery Status

Completed on 2026-06-05:

- Added six prompt files under `prompts/agents/`.
- Added `AgentPromptVersion` ORM model and migration `20260605_0009_agent_prompt_version.py`.
- Added `prompt_registry.py` for prompt hash/version sync and active prompt lookup.
- Added deterministic route-only service `services/agents/router.py`.
- Added `POST /api/v1/agent/ask`.
- Added prompt registration to `seed_demo_data.py`.
- Added tests:
  - `backend/tests/services/test_agent_prompt_versions.py`
  - `backend/tests/services/test_agent_router.py`
  - `backend/tests/api/test_agent_ask_api.py`

Verification:

- RED confirmed: target tests initially failed on missing `AgentPromptVersion` and missing `prompt_registry`.
- Targeted 2.4-A tests: passed.
- Alembic upgrade head: passed through `20260605_0009`.
- Schema check: 21 ORM tables match the database.
- Full backend pytest: passed.
