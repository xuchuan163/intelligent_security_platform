# 13 Phase 2 NL2SQL Benchmark Design

## Scope

Phase 2 Task 2.3-D only. This slice adds a 100+ case NL2SQL benchmark dataset and an internal benchmark runner.

The benchmark evaluates candidate SQL generation and SQL safety gating. It does not expose `/api/v1/agent/nl2sql`, does not execute SQL, and does not connect the feature to the frontend or six-Agent orchestration.

## Preconditions

- 2.3-A SQL audit is complete.
- 2.3-B read-only executor is complete but is not used by this benchmark.
- 2.3-C mock and Qwen providers are complete.
- Real Qwen smoke has shown that Qwen output can become candidate SQL and still pass through `audit_sql`.

## Dataset

Add:

`backend/tests/datasets/nl2sql_100.jsonl`

Each line is one JSON object with:

- `case_id`
- `category`
- `question`
- `mock_llm_output`
- `expected_status`
- `expected_tables`
- `expected_fields`
- `expected_contains`
- `forbidden_contains`
- `requires_clarification`
- `difficulty`

The dataset must contain at least 100 cases and cover:

- Normal project, worker, subcontractor, hazard, equipment, work-order queries.
- Metric semantic questions.
- Approved joins.
- Ambiguous questions that should request clarification.
- Unsafe SQL attempts that must be blocked.
- Invalid LLM output formats.

## Metrics

The benchmark runner reports:

- `total_cases`
- `passed_cases`
- `failed_cases`
- `generation_valid_rate`
- `audit_pass_rate`
- `unsafe_block_rate`
- `clarification_rate`
- `invalid_output_block_rate`
- `category_summary`
- `failures`

Definitions:

- `generation_valid_rate`: cases ending as `audit_passed`, `audit_rejected`, or `clarification_required`.
- `audit_pass_rate`: expected legal SQL cases that passed audit.
- `unsafe_block_rate`: expected `audit_rejected` cases that were rejected.
- `clarification_rate`: expected clarification cases that returned `clarification_required`.
- `invalid_output_block_rate`: expected invalid-output cases that returned `invalid_output` or `generation_failed`.

## Runner

Add:

`backend/app/services/nl2sql/benchmark.py`

The runner should:

- Load JSONL cases.
- Use `MockCandidateSqlProvider(case["mock_llm_output"])`.
- Call `generate_candidate_sql`.
- Compare status, tables, fields, required SQL fragments, and forbidden SQL fragments.
- Produce a deterministic in-memory report.
- Never execute SQL.
- Never write audit rows.
- Never call real Qwen during normal pytest.

## Acceptance Criteria

- `nl2sql_100.jsonl` contains at least 100 cases.
- Dataset categories cover legal, ambiguous, unsafe, and invalid-output scenarios.
- Benchmark tests pass without network access.
- Unsafe block rate is 100% for the static mock dataset.
- No API route is added.
- `/api/v1/agent/nl2sql` remains unimplemented.

## Planned TDD Work

1. Add benchmark tests and dataset.
2. Run tests and confirm RED because benchmark runner is missing.
3. Implement the smallest runner that passes the tests.
4. Run NL2SQL test group.
5. Run full backend pytest.

## Next Review Gate

After 2.3-D passes, review whether to improve prompts and case coverage or proceed to an explicit `/agent/nl2sql` endpoint design. Do not expose an endpoint without a separate contract, permission, rate-limit, and audit-log review.

## Delivery Status

Completed on 2026-06-04:

- Added `backend/tests/datasets/nl2sql_100.jsonl` with 105 benchmark cases.
- Added `backend/app/services/nl2sql/benchmark.py`.
- Added `backend/tests/services/test_nl2sql_benchmark.py`.
- Benchmark uses `MockCandidateSqlProvider` and `generate_candidate_sql`.
- Benchmark does not call Qwen, execute SQL, write audit rows, or expose an API.
- Unsafe outputs are counted as blocked when they end as `audit_rejected`, `invalid_output`, or `generation_failed`.

Verification:

- RED confirmed: benchmark tests initially failed because `benchmark.py` was missing.
- `pytest tests/services/test_nl2sql_benchmark.py -q`: 3 passed.
- `pytest tests/services/test_nl2sql_auditor.py tests/services/test_nl2sql_executor.py tests/services/test_nl2sql_prompt_builder.py tests/services/test_nl2sql_generator.py tests/services/test_nl2sql_qwen_provider.py tests/services/test_nl2sql_benchmark.py -q`: 27 passed.
- `pytest -q`: 91 passed.
