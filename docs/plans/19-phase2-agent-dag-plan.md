# Phase 2.4-C Agent DAG Plan-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `plan_only` mode to `/api/v1/agent/ask` that returns auditable DAG `planned_steps` without executing any node.

**Architecture:** Keep the FastAPI endpoint thin and extend `backend/app/services/agents/router.py` with deterministic planning helpers. The existing classifier remains the source of truth; plan generation only describes what a future orchestrator would do.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy session injection, pytest.

---

## Scope

In scope:

- Extend `AgentAskRequest.execution_mode` with `plan_only`.
- Add deterministic DAG plan generation to `route_agent_message`.
- Return `planned_steps`, `dag_status`, and `dag_execution_allowed`.
- Update tests, README, and roadmap.

Out of scope:

- No sub-agent execution.
- No DAG runtime.
- No parallelism.
- No automatic tool, SQL, NL2SQL, or work-order execution.
- No new database tables or Alembic migration.

## Files

- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/services/agents/router.py`
- Modify: `backend/tests/services/test_agent_router.py`
- Modify: `backend/tests/api/test_agent_ask_api.py`
- Modify: `docs/IMPLEMENTATION_ROADMAP.md`
- Modify: `README.md`

## Tasks

### Task 1: RED Service Tests

- [x] Add `test_plan_only_returns_auditable_dag_steps_without_execution` to `backend/tests/services/test_agent_router.py`.
- [x] Add `test_plan_only_nl2sql_references_guarded_api_without_sql_execution` to `backend/tests/services/test_agent_router.py`.
- [x] Add `test_plan_only_restricted_action_marks_review_on_route_and_steps` to `backend/tests/services/test_agent_router.py`.
- [x] Run:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests\services\test_agent_router.py -q
```

Expected before implementation: tests fail because `plan_only` metadata and steps do not exist.

### Task 2: RED API Test

- [x] Add `test_agent_ask_plan_only_returns_planned_steps` to `backend/tests/api/test_agent_ask_api.py`.
- [x] Run:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests\api\test_agent_ask_api.py -q
```

Expected before implementation: request validation rejects `plan_only` or response lacks DAG metadata.

### Task 3: Implement Plan-Only Mode

- [x] Update `backend/app/schemas/agent.py`:

```python
execution_mode: Literal["route_only", "execute_preview", "plan_only"] = "route_only"
```

- [x] Add `_build_planned_steps(route_result)` helper in `backend/app/services/agents/router.py`.
- [x] In `route_agent_message`, when `execution_mode == "plan_only"`, add:

```python
{
    "dag_status": "planned",
    "dag_execution_allowed": False,
    "planned_steps": _build_planned_steps(result),
}
```

- [x] Ensure every step has `will_execute=False`.
- [x] Ensure restricted actions force relevant `requires_human_review=True`.

### Task 4: GREEN Verification

- [x] Run targeted tests:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests\services\test_agent_router.py tests\api\test_agent_ask_api.py -q
```

- [x] Run schema check:

```bash
cd backend
..\.venv\Scripts\python.exe scripts\check_db_schema.py
```

- [x] Run full backend tests:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

### Task 5: Docs and Roadmap

- [x] Update `docs/IMPLEMENTATION_ROADMAP.md` Phase 2.4 status with 2.4-C plan-only completion.
- [x] Update `README.md` with a `plan_only` curl example and the non-execution boundary.
- [x] Mark this plan's task checkboxes complete only after verification commands pass.

## Acceptance

- `plan_only` response is deterministic and auditable.
- `planned_steps` exists and all steps have `will_execute=false`.
- NL2SQL branch references the guarded API only.
- Restricted action language keeps human-review requirements.
- No database schema changes are introduced.
