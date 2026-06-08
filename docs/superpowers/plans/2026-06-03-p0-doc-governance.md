# P0 Documentation Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the repository with the approved P0 documentation and collaboration framework.

**Architecture:** Keep application code untouched. Add missing P0 documentation, generate an OpenAPI snapshot from the running FastAPI app, and add README placeholders for future config/prompt directories.

**Tech Stack:** Markdown, FastAPI OpenAPI generation, Python standard library.

---

### Task 1: Create Missing P0 Documentation

**Files:**
- Create: `docs/ACCEPTANCE_CRITERIA.md`
- Create: `docs/architecture/C4_AND_DEPLOYMENT.md`
- Create: `docs/domain/ENUMS_AND_CONSTANTS.md`
- Create: `docs/database/SCHEMA_BASELINE.md`

- [ ] **Step 1: Add acceptance criteria for MVP demo readiness**
- [ ] **Step 2: Add C4/deployment view for current local architecture**
- [ ] **Step 3: Add enums/constants baseline for risk levels, work orders, rules, and API codes**
- [ ] **Step 4: Add schema baseline for current 15 ORM tables**

### Task 2: Add Future Directory Placeholders

**Files:**
- Create: `config/rules/README.md`
- Create: `config/metrics/README.md`
- Create: `prompts/README.md`

- [ ] **Step 1: Explain rules config is P1 and not yet active**
- [ ] **Step 2: Explain metrics config is P1 and DB remains current source**
- [ ] **Step 3: Explain prompts are P2 and current prompt lives in backend service code**

### Task 3: Generate OpenAPI Snapshot

**Files:**
- Create: `docs/api/openapi.yaml`

- [ ] **Step 1: Export `app.openapi()` to YAML**
- [ ] **Step 2: Verify the snapshot includes core paths such as `/api/v1/health`, `/api/v1/work-orders`, and `/api/v1/metrics/catalog`**

### Task 4: Refresh Existing P0 Status

**Files:**
- Modify: `docs/IMPLEMENTATION_ROADMAP.md`
- Modify: `docs/MVP_SCOPE.md`

- [ ] **Step 1: Update metrics status to reflect DB-backed catalog API**
- [ ] **Step 2: Update database table count wording from 12 to 15 where needed**

### Task 5: Verify

- [ ] **Step 1: Run backend tests**

Run: `..\.venv\Scripts\python.exe -m pytest -v`

- [ ] **Step 2: Run frontend build**

Run: `npm run build`

- [ ] **Step 3: Verify OpenAPI snapshot can be parsed by Python YAML if available or contains key paths as text**

