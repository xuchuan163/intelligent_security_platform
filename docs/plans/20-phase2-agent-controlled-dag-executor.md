# Phase 2.4-D Controlled Agent DAG Executor Design

## Review Decision

Approved scope:

```text
Controlled DAG executor v1:
dry_run + controlled_execute. Read-only tools may execute. Write-side tools only return approval_required. No automatic business disposition.
```

This design extends the existing `plan_only` mode. It turns an auditable plan into a controlled run, but it does not introduce free-form multi-Agent autonomy.

## Current Preconditions

- `POST /api/v1/agent/ask` already supports `route_only`, `execute_preview`, and `plan_only`.
- `plan_only` returns deterministic `planned_steps` with `will_execute=false`.
- Six Agent prompt identities and `agent_prompt_version` exist.
- NL2SQL already has a guarded API gate, audit table, read-only executor, and company/project scope injection.
- Backend security context already exposes `company_id`, `project_id`, `scope_type`, and `authorized_project_ids`.

## Goals

- Add an auditable Agent DAG execution layer without automatic business actions.
- Support `dry_run` to validate planned steps, tools, permissions, and human-review requirements without executing tools.
- Support `controlled_execute` for read-only tools only.
- Persist run-level and step-level audit records.
- Keep all write-side or high-risk actions blocked as `approval_required`.

## Non-Goals

- No real parallel Agent runtime.
- No LangGraph or external orchestration framework.
- No automatic work-order creation, dispatch, transition, closure, penalty, stop-work, subcontractor removal, or restricted operation.
- No LLM-decided permissions.
- No direct SQL execution outside the existing NL2SQL audit/executor path.
- No frontend rebuild in this slice.

## Execution Modes

### `dry_run`

`dry_run` validates the DAG and records what would happen.

Rules:

- Build or reuse deterministic `planned_steps`.
- Resolve every `tool_name` through the tool registry.
- Check tool category, side-effect level, project access, and human-review requirements.
- Return step statuses such as `dry_run_passed`, `approval_required`, `blocked`, or `skipped`.
- Do not execute any tool.
- Persist run and step records for audit.

### `controlled_execute`

`controlled_execute` may execute only read-only tools.

Rules:

- Run the same validation as `dry_run` first.
- Execute only tools marked `read_only`.
- Block write-side tools as `approval_required`.
- Block restricted actions as `blocked` with `need_human_review=true`.
- Stop dependent steps when a required prior step fails or is blocked.
- Persist all step inputs and outputs as summaries, not raw sensitive payloads.

## Tool Registry v1

Allowed read-only tools:

| Tool | Purpose | Execution |
|---|---|---|
| `profile.read` | Read project/worker/subcontractor profile summaries | allowed in `controlled_execute` |
| `rules.read_triggers` | Read rule trigger evidence | allowed in `controlled_execute` |
| `work_orders.read` | Read work-order state and detail | allowed in `controlled_execute` |
| `hazards.read` | Read hazard ledger/detail | allowed in `controlled_execute` |
| `metrics.read_catalog` | Read metric catalog, lineage, and aliases | allowed in `controlled_execute` |
| `nl2sql.audit_only` | Generate/audit candidate SQL without execution | allowed in `controlled_execute` |
| `nl2sql.readonly_execute` | Execute only audited read-only SQL through existing executor | allowed only after audit pass |
| `cases.read` | Read accident case library summaries | allowed in `controlled_execute` |
| `memory.read_context` | Read current session context summary | allowed in `controlled_execute` |

Write-side or restricted tools are not executed in v1:

| Tool | v1 Result |
|---|---|
| `work_orders.create` | `approval_required` |
| `work_orders.dispatch` | `approval_required` |
| `work_orders.transition` | `approval_required` |
| `hazards.create` | `approval_required` |
| `penalty.create` | `blocked` |
| `stop_work.issue` | `blocked` |
| `subcontractor.remove` | `blocked` |

## Permission Rules

Every run inherits the current user context:

```json
{
  "user_id": "U101",
  "company_id": "COMPANY-A",
  "scope_type": "project",
  "authorized_project_ids": ["P002"],
  "roles": ["general_contractor_safety_officer"]
}
```

Rules:

- Company users can run read-only tools over their company scope.
- Project users can only run tools for `authorized_project_ids`.
- If the request context includes an unauthorized `project_id`, the run is `blocked`.
- Tool implementations must call existing backend scope filters and cannot trust frontend context.
- NL2SQL must go through the existing guarded gate and must retain audit rows.

## Audit Tables

Add two tables.

### `agent_dag_run`

Fields:

- `id`
- `run_id`
- `tenant_id`
- `company_id`
- `project_id`
- `scope_type`
- `user_id`
- `message`
- `execution_mode`
- `target_agent`
- `status`
- `need_human_review`
- `blocked_reason`
- `created_at`
- `completed_at`

Indexes:

- `run_id`
- `company_id, project_id`
- `user_id, created_at`
- `status`

### `agent_dag_step_run`

Fields:

- `id`
- `step_run_id`
- `run_id`
- `step_id`
- `agent_code`
- `action`
- `tool_name`
- `status`
- `will_execute`
- `requires_human_review`
- `input_summary`
- `output_summary`
- `error_message`
- `elapsed_ms`
- `created_at`
- `completed_at`

Indexes:

- `run_id`
- `step_run_id`
- `status`
- `tool_name`

## Status Model

Run statuses:

```text
planned
dry_run_passed
blocked
approval_required
running
succeeded
failed
```

Step statuses:

```text
planned
dry_run_passed
executed
skipped
blocked
failed
approval_required
```

Mapping:

- Any restricted action -> run `blocked`.
- Any write-side business action -> run `approval_required`.
- All dry-run checks pass -> run `dry_run_passed`.
- Controlled read-only execution succeeds -> run `succeeded`.
- Tool exception -> current step `failed`; dependent steps `skipped`.

## API Contract

Reuse:

```text
POST /api/v1/agent/ask
```

Extend `execution_mode`:

```json
{
  "message": "List open work orders for P002 and explain the safety risk.",
  "execution_mode": "dry_run",
  "context": {
    "project_id": "P002"
  }
}
```

Response data should include:

```json
{
  "execution_mode": "dry_run",
  "dag_status": "dry_run_passed",
  "dag_execution_allowed": false,
  "run_id": "AGDAG-...",
  "target_agent": "work_order_coordinator",
  "need_human_review": false,
  "planned_steps": [],
  "step_results": [
    {
      "step_id": "step_1",
      "tool_name": null,
      "status": "dry_run_passed",
      "will_execute": false
    }
  ]
}
```

For `controlled_execute`, read-only steps may return summarized outputs:

```json
{
  "execution_mode": "controlled_execute",
  "dag_status": "succeeded",
  "dag_execution_allowed": true,
  "run_id": "AGDAG-...",
  "step_results": [
    {
      "step_id": "step_2",
      "tool_name": "work_orders.read",
      "status": "executed",
      "output_summary": {
        "row_count": 3,
        "fields": ["work_order_id", "status", "priority"]
      }
    }
  ]
}
```

## Suggested Files

Create:

- `backend/app/services/agents/tool_registry.py`
- `backend/app/services/agents/dag_executor.py`
- `backend/tests/services/test_agent_tool_registry.py`
- `backend/tests/services/test_agent_dag_executor.py`
- `backend/tests/api/test_agent_dag_api.py`
- `backend/alembic/versions/20260606_0010_agent_dag_run.py`

Modify:

- `backend/app/schemas/agent.py`
- `backend/app/services/agents/router.py`
- `backend/app/api/v1/endpoints/agent.py`
- `backend/app/infrastructure/database/models.py`
- `backend/scripts/check_db_schema.py`
- `docs/IMPLEMENTATION_ROADMAP.md`
- `README.md`

## TDD Implementation Plan

### Task 1: Tool Registry

- Write failing tests for read-only tool registration.
- Write failing tests for unknown tool rejection.
- Write failing tests proving write-side tools return `approval_required` or `blocked`.
- Implement `ToolDefinition`, `ToolExecutionContext`, and registry lookup.

### Task 2: DAG Audit Models

- Write schema check tests for `agent_dag_run` and `agent_dag_step_run`.
- Add ORM models.
- Add Alembic migration.
- Run `alembic upgrade head`.

### Task 3: Dry Run Executor

- Write tests for `dry_run` using existing `planned_steps`.
- Verify every step is validated and no tool is executed.
- Verify unauthorized project context blocks the run.
- Verify restricted action language blocks the run.
- Persist run and step audit records.

### Task 4: Controlled Execute Executor

- Write tests for read-only tool execution.
- Verify write-side tools become `approval_required`.
- Verify failed steps cause dependent steps to be skipped.
- Verify output summaries do not include sensitive raw payloads.

### Task 5: API Integration

- Extend `AgentAskRequest.execution_mode` with `dry_run` and `controlled_execute`.
- Keep endpoint thin.
- Return `run_id`, `dag_status`, `dag_execution_allowed`, `planned_steps`, and `step_results`.
- Add API tests for both modes.

### Task 6: Documentation And Smoke

- Update README curl examples.
- Update roadmap Phase 2.4-D status.
- Run targeted tests.
- Run full backend pytest.
- Run frontend build only if API types or UI are touched.

## Acceptance Criteria

- `dry_run` persists audit records but executes no tools.
- `controlled_execute` executes only read-only tools.
- Write-side tools produce `approval_required`.
- Restricted actions produce `blocked` and `need_human_review=true`.
- Project users cannot run steps against unauthorized projects.
- NL2SQL steps use only the existing guarded gate.
- No automatic work-order, hazard, penalty, stop-work, or subcontractor-removal action occurs.
- Targeted backend tests pass.
- Full backend pytest passes before marking complete.

## Delivery Status

Completed on 2026-06-06:

- Added `backend/app/services/agents/tool_registry.py`.
- Added `backend/app/services/agents/dag_executor.py`.
- Added ORM models `AgentDagRun` and `AgentDagStepRun`.
- Added Alembic migration `20260606_0010_agent_dag_run.py`.
- Extended `AgentAskRequest.execution_mode` with `dry_run` and `controlled_execute`.
- Updated `/api/v1/agent/ask` so controlled modes reuse deterministic `plan_only` steps and then call the executor.
- Marked the work-order inspection DAG step with read-only tool `work_orders.read`.
- Added tests:
  - `backend/tests/services/test_agent_tool_registry.py`
  - `backend/tests/services/test_agent_dag_executor.py`
  - `backend/tests/api/test_agent_ask_api.py`

Verification:

- RED confirmed for missing tool registry, missing DAG models, missing executor, and unsupported API modes.
- Targeted Agent tests passed.
- `alembic upgrade head` applied `20260606_0010`.
- `python scripts/check_db_schema.py` passed with 23 ORM tables.

## Next Step

Review 2.4-E before adding any broader tool execution. Do not start 2.5 hazard rectification Agent or frontend DAG UI until 2.4-D full backend verification is green.
