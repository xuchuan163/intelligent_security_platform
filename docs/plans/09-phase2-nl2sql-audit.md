# 09 Phase 2 NL2SQL Audit Plan

## Scope

Phase 2 Task 2.3-A only. This slice builds the SQL safety gate required before NL2SQL is exposed.

## Delivered Contract

- SQL AST audit service based on `sqlglot`.
- `agent_nl2sql_audit` table for audit logs.
- Table whitelist for Phase 1/2 business tables.
- Field whitelist with explicit sensitive-field blacklist.
- Only single `SELECT` statements are allowed.
- Multi-statement SQL, write SQL, `SELECT *`, blocked tables, blocked fields, and tenant override are rejected.
- `tenant_id` is injected for every whitelisted tenant-scoped table.
- `org_path LIKE current_user.org_path + '%'` is injected for org-scoped users.
- Missing `LIMIT` becomes `LIMIT 100`; oversized limits are capped at `LIMIT 500`.
- `backend/tests/datasets/nl2sql_audit_cases.jsonl` contains 30 security audit cases.

## Explicit Non-Goals

- No `/api/v1/agent/nl2sql` endpoint.
- No LLM-generated SQL.
- No SQL execution.
- No natural language clarification flow.
- No 100+ NL2SQL accuracy benchmark yet.

## Next Gate

Before 2.3-B, review whether to add a read-only executor. The executor must call this audit service first and must write execution status back to `agent_nl2sql_audit`.
