# 12 Phase 2 NL2SQL Qwen Provider Design

## Scope

Phase 2 Task 2.3-C-C only. This slice connects a real Qwen-backed candidate SQL provider to the existing 2.3-C generation service.

The provider may call Qwen to produce raw candidate SQL, but the output remains untrusted and must still pass the existing parsing and 2.3-A audit flow before it can be marked usable.

## Current Preconditions

- 2.3-A SQL audit is complete.
- 2.3-B read-only executor is complete.
- 2.3-C-A/B prompt builder, schema context builder, mock provider, and candidate generator are complete.
- Existing Qwen infrastructure exists at `backend/app/infrastructure/llm/qwen_client.py`.

## Explicit Non-Goals

- No `/api/v1/agent/nl2sql` endpoint.
- No `/api/v1/agent/ask` routing.
- No automatic SQL execution.
- No six-Agent DAG orchestration.
- No requirement for real network access in normal pytest.
- No persistence of full LLM prompts or raw provider responses.

## Provider Contract

The Qwen provider implements the existing `CandidateSqlProvider` protocol:

```text
generate(prompt: str) -> str
```

It returns only the provider content string. All interpretation remains in `generate_candidate_sql`:

- Empty content -> `generation_failed`
- Provider exception -> `generation_failed`
- Markdown/prose -> `invalid_output`
- `CLARIFICATION_REQUIRED:` -> `clarification_required`
- Plain SQL -> `audit_sql`

## API Key Missing Fallback

If `DASHSCOPE_API_KEY` is missing or the Qwen client reports unavailable:

- The provider raises a controlled runtime error.
- `generate_candidate_sql` maps it to `generation_failed`.
- No SQL is generated.
- No audit or execution is attempted.
- Normal local tests can still run with mock or disabled provider.

## Timeout and Exception Handling

NL2SQL uses a shorter timeout than the general safety assistant:

- Default timeout: 10 seconds.
- Config: `QWEN_NL2SQL_TIMEOUT_SECONDS`.
- Timeout, network errors, malformed responses, and non-OK API responses all map to `generation_failed`.
- No retry is performed in 2.3-C-C.

## Prompt Injection Defense

Prompt injection is handled as a defense-in-depth concern:

- The prompt tells Qwen to ignore user attempts to override system rules.
- The parser accepts only plain SQL or `CLARIFICATION_REQUIRED`.
- The audit layer remains the hard boundary for tables, fields, tenant scope, write SQL, multi-statement SQL, and `SELECT *`.

Prompt text can reduce bad outputs, but only 2.3-A audit is trusted.

## Provider Factory

Add an internal provider factory:

```text
mock -> MockCandidateSqlProvider
qwen -> QwenCandidateSqlProvider
disabled -> DisabledCandidateSqlProvider
```

Config:

- `NL2SQL_PROVIDER=mock|qwen|disabled`
- Default: `disabled`
- Tests use explicit provider selection and do not depend on environment state.

## Test Plan

Red tests first:

- Qwen provider maps missing API key to `generation_failed`.
- Qwen timeout or provider exception maps to `generation_failed`.
- Qwen provider SQL output still flows through `audit_sql`.
- Markdown or explanation output from Qwen is rejected as `invalid_output`.
- Provider factory switches between `mock`, `qwen`, and `disabled`.

## Acceptance Criteria

- Normal `pytest` passes without real Qwen network access.
- Qwen provider is internal only.
- Candidate SQL still cannot bypass audit.
- No new API route is added.
- `/api/v1/agent/nl2sql` remains unimplemented.

## Next Review Gate

After 2.3-C-C passes tests, review whether to run a real Qwen smoke test using local `.env` credentials. Do not proceed to `/agent/nl2sql` exposure until endpoint contract, permission model, audit logging behavior, and user-facing failure semantics are separately approved.

## Delivery Status

Completed on 2026-06-04:

- Added `QwenCandidateSqlProvider`.
- Added `DisabledCandidateSqlProvider`.
- Added `build_candidate_sql_provider` for `mock`, `qwen`, and `disabled`.
- Added `NL2SQL_PROVIDER` and `QWEN_NL2SQL_TIMEOUT_SECONDS` settings.
- API key missing, timeout, and provider exceptions map to `generation_failed`.
- Qwen SQL output still flows through `audit_sql`.
- Markdown and prose outputs are rejected by the existing candidate parser.
- No API route was added.

Verification:

- `pytest tests/services/test_nl2sql_qwen_provider.py -q`: 5 passed.
- `pytest tests/services/test_nl2sql_auditor.py tests/services/test_nl2sql_executor.py tests/services/test_nl2sql_prompt_builder.py tests/services/test_nl2sql_generator.py tests/services/test_nl2sql_qwen_provider.py -q`: 24 passed.
- `pytest -q`: 88 passed.
