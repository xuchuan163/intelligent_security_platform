# Phase 2 Agent Main Controller Preview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `execute_preview` mode to `/api/v1/agent/ask`, using active prompt text and Qwen to generate a structured route explanation without running DAG orchestration or tools.

**Architecture:** `route_only` remains deterministic and default. `execute_preview` first computes the deterministic route, then loads the active prompt file and asks Qwen for a JSON preview. LLM output is attached as advisory metadata and cannot change deterministic route or downgrade human-review requirements.

**Tech Stack:** FastAPI, Pydantic v2, existing Qwen client, SQLAlchemy prompt registry, pytest.

---

## Task 1: RED Tests

**Files:**
- Modify: `backend/tests/services/test_agent_router.py`
- Modify: `backend/tests/api/test_agent_ask_api.py`

- [x] Add service test for `execute_preview` with a fake available Qwen client returning valid JSON.
- [x] Add service test for unavailable Qwen returning `preview_status="llm_unavailable"`.
- [x] Add service test proving restricted-action language keeps `need_human_review=true` even if LLM returns false.
- [x] Add API test for `execution_mode="execute_preview"`.
- [x] Run targeted tests and confirm RED because `execution_mode` and preview service are missing.

## Task 2: Schema And Service

**Files:**
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/services/agents/router.py`

- [x] Add `execution_mode: Literal["route_only", "execute_preview"] = "route_only"` to `AgentAskRequest`.
- [x] Add optional `llm_client` parameter to route service for tests.
- [x] Load active prompt text from `prompt_path`.
- [x] Build a compact controller prompt with output JSON requirements.
- [x] Parse JSON preview output.
- [x] Return stable preview fields for generated, unavailable, and invalid output cases.

## Task 3: Endpoint

**Files:**
- Modify: `backend/app/api/v1/endpoints/agent.py`

- [x] Pass `body.execution_mode` to the route service.
- [x] Keep endpoint thin and return `success()`.

## Task 4: Docs And Verification

**Files:**
- Modify: `docs/IMPLEMENTATION_ROADMAP.md`
- Modify: `README.md`
- Modify: `docs/plans/18-phase2-agent-main-controller-preview.md`

- [x] Record 2.4-B delivery status.
- [x] Add README example for `execute_preview`.
- [x] Run targeted tests.
- [x] Run schema check.
- [x] Run full backend pytest.

Commands:

```bash
cd backend
..\.venv\Scripts\python.exe -m pytest tests\services\test_agent_router.py tests\api\test_agent_ask_api.py -q
..\.venv\Scripts\python.exe scripts\check_db_schema.py
..\.venv\Scripts\python.exe -m pytest -q
```

## Acceptance

- `/api/v1/agent/ask` defaults to `route_only`.
- `execute_preview` reads the active prompt file and calls Qwen.
- Qwen unavailable returns a safe preview-unavailable response.
- Invalid LLM output is not treated as structured preview.
- LLM output cannot change deterministic `target_agent`.
- LLM output cannot downgrade restricted-action `need_human_review`.
- No DAG, tool execution, SQL execution, or work-order creation is introduced.

## Delivery Status

Completed on 2026-06-05:

- Added `execution_mode` to `AgentAskRequest`.
- Extended `route_agent_message` with `execute_preview`, active prompt loading, Qwen preview call, JSON preview parsing, and unavailable/invalid-output fallbacks.
- Updated `/api/v1/agent/ask` to pass execution mode.
- Added tests for generated preview, unavailable LLM, restricted-action human-review preservation, and API preview response.

Verification:

- RED confirmed: target tests initially failed because `route_agent_message` did not accept `execution_mode` and the router had no `qwen` preview dependency.
- Targeted tests: passed.
- Schema check: passed.
- Full backend pytest: passed.
