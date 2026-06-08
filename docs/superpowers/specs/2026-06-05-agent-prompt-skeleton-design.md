# Agent Prompt Version And Skeleton Design

## Purpose

Phase 2 Task 2.4-A establishes the static identity and routing boundary for six safety-platform agents. It does not implement multi-agent orchestration, DAG execution, tool calling, or automatic work-order creation.

## Scope

In scope:

- Six prompt files under `prompts/agents/`.
- `agent_prompt_version` ORM model and Alembic migration.
- Seed/sync logic that registers one active prompt version per agent.
- Prompt service functions to list active prompt versions and resolve one active prompt by `agent_code`.
- Intent router service that maps a user question to one target agent and returns `execution_mode="route_only"`.
- `POST /api/v1/agent/ask` route preview endpoint.
- Tests for prompt registration, route selection, human-review boundaries, and API response shape.

Out of scope:

- No LangGraph, LangChain, DAG, parallel execution, or sub-agent calls.
- No automatic SQL execution from `/agent/ask`.
- No automatic stop-work, penalty, subcontractor removal, or work-order creation.
- No prompt editing UI.
- No feedback table in this slice.

## Six Agents

- `safety_supervisor`: main route preview and safety policy coordinator.
- `risk_profile_analyst`: explains project, worker, and subcontractor risk profiles.
- `rule_compliance_checker`: explains strong-rule triggers and compliance evidence.
- `work_order_coordinator`: explains work-order status, overdue state, and closure actions.
- `nl2sql_analyst`: handles metric and data-query intent, but only routes to the guarded NL2SQL gate.
- `hazard_rectification_advisor`: drafts hazard rectification suggestions with evidence and human review.

## Data Model

`agent_prompt_version` stores immutable prompt registrations:

- `agent_code`
- `prompt_version`
- `prompt_path`
- `prompt_hash`
- `status`
- `is_active`
- `created_at`
- `updated_at`

The service treats `(agent_code, prompt_version)` as unique. Exactly one active prompt is expected per agent in local seed data.

## Routing Contract

`POST /api/v1/agent/ask` accepts:

```json
{
  "message": "查询 P001 项目风险最高的工单",
  "context": {"project_id": "P001"}
}
```

It returns:

```json
{
  "intent": "work_order",
  "target_agent": "work_order_coordinator",
  "prompt_version": "v1.0",
  "route_reason": "message mentions work orders",
  "execution_mode": "route_only",
  "need_human_review": false,
  "blocked_actions": []
}
```

Any stop-work, penalty, subcontractor removal, or disciplinary language forces `need_human_review=true` and includes the reason in `blocked_actions`.

## Testing

- Schema test: model metadata includes `agent_prompt_version`.
- Prompt service test: sync registers six active prompts and stable hashes.
- Router service test: representative messages route to all six agents.
- Safety boundary test: punitive/stop-work language requires human review.
- API test: `/api/v1/agent/ask` returns `SUCCESS` and route-only output.

