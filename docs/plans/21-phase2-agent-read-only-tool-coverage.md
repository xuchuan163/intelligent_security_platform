# Phase 2.4-E Agent Read-Only Tool Coverage

## Scope

This slice extends the controlled DAG executor from 2.4-D with broader read-only tool execution.

Implemented read-only tools:

- `profile.read`
- `rules.read_triggers`
- `hazards.read`
- `metrics.read_catalog`

Existing read-only tool retained:

- `work_orders.read`

## Non-Goals

- No write-side tool execution.
- No automatic work-order creation, dispatch, transition, or closure.
- No automatic hazard creation or closure.
- No penalty, stop-work, subcontractor removal, or restricted operation.
- No default execution of `nl2sql.readonly_execute`.
- No frontend DAG UI.

## Output Contract

Read-only tools return bounded summaries:

```json
{
  "row_count": 1,
  "fields": ["id", "status"],
  "items": [
    {"id": "P001", "status": "active"}
  ],
  "truncated": false
}
```

Rules:

- Maximum 20 business items per tool execution.
- Fields are explicit allowlists.
- No binary file content.
- No local file paths.
- No sensitive identity, health, face image, or raw video fields.
- Large evidence JSON is not returned.

## Planner Mapping

`plan_only`, `dry_run`, and `controlled_execute` now use these tool mappings:

| Agent branch | Read-only tool |
|---|---|
| `risk_profile_analyst` | `profile.read` |
| `rule_compliance_checker` | `rules.read_triggers` |
| `hazard_rectification_advisor` | `hazards.read` |
| `nl2sql_analyst` | `metrics.read_catalog`, then guarded `nl2sql.audit_only` |
| `work_order_coordinator` | `work_orders.read` |

## Delivery Status

Completed on 2026-06-06:

- Added service tests in `backend/tests/services/test_agent_read_tools.py`.
- Extended `backend/app/services/agents/dag_executor.py` with summary execution for:
  - `profile.read`
  - `rules.read_triggers`
  - `hazards.read`
  - `metrics.read_catalog`
- Updated `backend/app/services/agents/router.py` so planned steps include the new read-only tool names.
- Extended `backend/tests/services/test_agent_router.py` for tool mapping.
- Extended `backend/tests/api/test_agent_ask_api.py` for controlled API execution across the broader read-only tool set.

Verification:

- RED confirmed: read-only tools initially returned empty summaries and planner steps lacked tool names.
- Targeted Agent read-tool/API tests passed.

## Next Step

Review 2.4-F before adding more tools. Keep all write-side tools at `approval_required` unless a separate approval workflow and human confirmation contract is implemented.
