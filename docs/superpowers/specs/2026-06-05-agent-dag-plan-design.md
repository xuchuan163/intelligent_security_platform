# Agent DAG Plan-Only Design

## Goal

Phase 2.4-C introduces an auditable Multi-Agent DAG planning shape for `/api/v1/agent/ask`, but it does not execute DAG nodes, call sub-agents, run tools, run SQL, create work orders, or parallelize any task.

## Scope

In scope:

- Add a new `execution_mode="plan_only"` to `/api/v1/agent/ask`.
- Keep deterministic main-controller routing as the source of truth for `intent`, `target_agent`, and `need_human_review`.
- Return `planned_steps` that describe the future orchestration path.
- Mark every planned node with `will_execute=false`.
- Return DAG metadata: `dag_status="planned"` and `dag_execution_allowed=false`.
- Preserve the existing `route_only` and `execute_preview` behavior.

Out of scope:

- No LangGraph, LangChain, Celery, Redis checkpoint orchestration, or parallel runtime.
- No automatic calls to the six agent services.
- No automatic NL2SQL execution; NL2SQL plans may only point to the guarded `/agent/nl2sql` gate.
- No automatic stop-work, penalty, subcontractor removal, restricted-work, or disciplinary action.

## API Contract

Request:

```json
{
  "message": "查询项目风险排名",
  "execution_mode": "plan_only",
  "context": {
    "project_id": "P001"
  }
}
```

Response data extends the existing route preview:

```json
{
  "intent": "nl2sql",
  "target_agent": "nl2sql_analyst",
  "execution_mode": "plan_only",
  "need_human_review": false,
  "dag_status": "planned",
  "dag_execution_allowed": false,
  "planned_steps": [
    {
      "step_id": "step_1",
      "agent_code": "safety_supervisor",
      "action": "classify_intent_and_route",
      "depends_on": [],
      "input_refs": ["message", "context"],
      "output_key": "route",
      "requires_human_review": false,
      "will_execute": false,
      "tool_name": null
    }
  ]
}
```

Each step must include:

- `step_id`
- `agent_code`
- `action`
- `depends_on`
- `input_refs`
- `output_key`
- `requires_human_review`
- `will_execute`
- `tool_name`

## Planning Rules

The first step is always `safety_supervisor/classify_intent_and_route`.

Then the deterministic target controls the branch:

- `nl2sql_analyst`: plan `prepare_guarded_nl2sql_request` and reference `POST /api/v1/agent/nl2sql`; still no SQL execution.
- `hazard_rectification_advisor`: plan evidence collection, rectification draft, and human review when restricted actions are present.
- `work_order_coordinator`: plan work-order state inspection and legal next-action identification; human review is required for restricted action language.
- `rule_compliance_checker`: plan rule-trigger evidence collection and explanation.
- `risk_profile_analyst`: plan profile evidence loading and risk-driver explanation.
- `safety_supervisor`: keep a general safety triage plan with no delegated execution.

Restricted action language keeps `need_human_review=true`, and relevant planned steps must also set `requires_human_review=true`.

## Testing

Add service tests for:

- `plan_only` returns `planned_steps`, `dag_status="planned"`, and `dag_execution_allowed=false`.
- Every planned step has `will_execute=false`.
- NL2SQL planning references the guarded API and does not expose SQL execution.
- Restricted-action language keeps `need_human_review=true` in both route result and planned steps.

Add API tests for:

- `/api/v1/agent/ask` accepts `execution_mode="plan_only"`.
- The response uses the standard `SUCCESS` wrapper and includes planned DAG metadata.

## Acceptance

- Targeted agent router/API tests pass.
- Full backend pytest passes.
- `scripts/check_db_schema.py` passes because this slice does not require database schema changes.
- Documentation and roadmap status are updated with the exact safe boundary.
