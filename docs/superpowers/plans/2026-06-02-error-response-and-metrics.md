# Error Response and Metrics API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add unified API error envelopes and read-only metrics catalog endpoints.

**Architecture:** Keep success responses unchanged. Add a small error response module and register global exception handlers in `app/main.py`; implement metrics as a standard router plus service and schema files.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Pytest.

---

### Task 1: Add Failing Tests

**Files:**
- Modify: `backend/tests/test_api_smoke.py`

- [ ] **Step 1: Add tests for unified error responses**

Test validation error on `POST /api/v1/work-orders` and 404 on an unknown route. Assert `code`, `message`, `request_id`, `data`, and `timestamp` exist, and `X-Request-Id` is preserved.

- [ ] **Step 2: Add tests for metrics routes**

Test `GET /api/v1/metrics/catalog` and `GET /api/v1/metrics/PROJECT_RISK_SCORE`.

- [ ] **Step 3: Run focused tests and verify RED**

Run: `..\.venv\Scripts\python.exe -m pytest tests\test_api_smoke.py -v`

Expected: failures because default FastAPI error bodies and metrics routes are not implemented.

### Task 2: Implement Unified Errors

**Files:**
- Create: `backend/app/core/errors.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Add error envelope helpers and code mapping**
- [ ] **Step 2: Register handlers for `HTTPException`, `RequestValidationError`, and generic `Exception`**
- [ ] **Step 3: Run focused tests and verify error tests pass**

### Task 3: Implement Metrics Read API

**Files:**
- Create: `backend/app/schemas/metrics.py`
- Create: `backend/app/services/metrics/service.py`
- Create: `backend/app/services/metrics/__init__.py`
- Create: `backend/app/api/v1/endpoints/metrics.py`
- Modify: `backend/app/api/v1/router.py`

- [ ] **Step 1: Add schemas for metric item, detail, and paged catalog**
- [ ] **Step 2: Add service queries for catalog and detail**
- [ ] **Step 3: Add router endpoints and mount `/metrics`**
- [ ] **Step 4: Run focused tests and verify metrics tests pass**

### Task 4: Final Verification

**Files:**
- No production code changes expected.

- [ ] **Step 1: Run backend tests**

Run: `..\.venv\Scripts\python.exe -m pytest -v`

- [ ] **Step 2: Compile backend**

Run: `..\.venv\Scripts\python.exe -m compileall app`

- [ ] **Step 3: Smoke test running API**

Check `/api/v1/metrics/catalog`, `/api/v1/metrics/PROJECT_RISK_SCORE`, and a 422 validation response.

