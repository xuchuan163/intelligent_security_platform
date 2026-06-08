# Agent Main Controller Preview Design

## Purpose

Phase 2 Task 2.4-B adds a prompt-backed preview mode to `/api/v1/agent/ask`. The endpoint can ask Qwen to produce a structured explanation for the already-determined route, while preserving the deterministic routing result from 2.4-A.

## Scope

In scope:

- Add `execution_mode` to `AgentAskRequest`, defaulting to `route_only`.
- Support `execution_mode="execute_preview"`.
- Load the active target-agent prompt from `agent_prompt_version.prompt_path`.
- Build a controller prompt from the active prompt, deterministic route result, user message, context, and safety boundary.
- Call Qwen through the existing `qwen` client.
- Parse JSON object output when available.
- Return `preview_status`, `llm_available`, `llm_message`, and `llm_preview`.
- Preserve deterministic `intent`, `target_agent`, `prompt_version`, `need_human_review`, and `blocked_actions`.

Out of scope:

- No DAG orchestration.
- No sub-agent execution.
- No NL2SQL execution.
- No work-order creation.
- No prompt editing UI.
- No new model provider abstraction in this slice.

## Behavior

`route_only` remains the default and returns the existing deterministic route result.

`execute_preview` returns the same route result plus:

```json
{
  "preview_status": "generated",
  "llm_available": true,
  "llm_message": "ok",
  "llm_preview": {
    "route_explanation": "why this target agent was selected",
    "expected_inputs": [],
    "evidence_needed": [],
    "safety_notes": [],
    "need_human_review": false
  }
}
```

If Qwen is unavailable, the endpoint still returns 200 with `preview_status="llm_unavailable"` and no preview object.

If Qwen returns non-JSON content, the endpoint returns `preview_status="invalid_llm_output"` and keeps the raw content out of the structured preview.

## Safety Rule

LLM output cannot downgrade `need_human_review`. If deterministic routing detects restricted action language, the final response keeps `need_human_review=true` even when LLM says otherwise.

