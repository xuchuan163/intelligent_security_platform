# Database Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create and verify the platform's local MySQL schema in `intelligent_security_platform`.

**Architecture:** Use the existing SQLAlchemy models as the source of truth. Update Alembic, runtime defaults, and seed behavior without adding unused future tables.

**Tech Stack:** MySQL 8, SQLAlchemy, Alembic, PyMySQL, FastAPI, Pytest.

---

### Task 1: Add Database Configuration Tests

**Files:**
- Modify: `backend/tests/test_api_smoke.py`

- [ ] **Step 1: Add tests for default database URL and safe reset default**

Assert `settings.database_url` contains `intelligent_security_platform`. Add a small test importing root `main.py` and asserting `MYSQL_DATABASE == "intelligent_security_platform"` and `RESET_DATABASE_ON_START is False`.

- [ ] **Step 2: Run focused tests and verify RED**

Run: `..\.venv\Scripts\python.exe -m pytest tests\test_api_smoke.py -v`

Expected: failure because current defaults still point to the old demo database and reset is enabled.

### Task 2: Update Runtime Defaults

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `main.py`
- Modify: `.env.example`

- [ ] **Step 1: Change default `database_url` to `intelligent_security_platform`**
- [ ] **Step 2: Change root `main.py` default database and port preference**
- [ ] **Step 3: Change `RESET_DATABASE_ON_START` default to disabled**
- [ ] **Step 4: Keep database URL/password logging masked**

### Task 3: Implement Real Initial Migration

**Files:**
- Modify: `backend/alembic/versions/20260602_0001_initial_schema.py`

- [ ] **Step 1: Replace no-op upgrade/downgrade with table create/drop logic from SQLAlchemy metadata**
- [ ] **Step 2: Ensure models are imported so all tables are registered**

### Task 4: Make Seed Idempotent

**Files:**
- Modify: `backend/scripts/seed_demo_data.py`

- [ ] **Step 1: Skip seed when tenant `CSCEC` already exists**
- [ ] **Step 2: Keep existing demo data content unchanged otherwise**

### Task 5: Verify Database and App

**Files:**
- No production code changes expected.

- [ ] **Step 1: Run Alembic upgrade against `intelligent_security_platform`**
- [ ] **Step 2: Run seed script twice**
- [ ] **Step 3: Inspect table count and key tables**
- [ ] **Step 4: Run backend tests**
- [ ] **Step 5: Run compileall**
- [ ] **Step 6: Restart `main.py` and smoke test API**

