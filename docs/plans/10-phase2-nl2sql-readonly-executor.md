# 10 Phase 2 NL2SQL Read-Only Executor Plan

## Scope

Phase 2 Task 2.3-B only. This slice adds an internal read-only executor that can run audited SQL safely.

## Delivered Contract

- The executor always calls the 2.3-A SQL audit service first.
- The executor only runs `sanitized_sql` returned by the audit service.
- Rejected audits are not executed and are logged as `execution_status = rejected`.
- Successful executions are logged as `execution_status = executed`.
- SQL execution failures are logged as `execution_status = failed`.
- Audit rows record `result_row_count`, `result_field_count`, and `execution_error`.
- Returned result sets are capped at 100 rows and 30 fields.
- Long text values are truncated to 500 characters.

## Explicit Non-Goals

- No `/api/v1/agent/nl2sql` endpoint.
- No LLM SQL generation.
- No natural-language ambiguity handling.
- No 100+ NL2SQL benchmark yet.
