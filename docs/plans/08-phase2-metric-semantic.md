# 08 Phase 2 Metric Semantic Layer Plan

## Scope

Phase 2 Task 2.2.x only. This slice strengthens the metric catalog contract for later NL2SQL, but does not generate SQL and does not expose `/agent/nl2sql`.

## Delivered Contract

- `POST /api/v1/metrics/validate`
  - Input: `{"metric_codes": ["PROJECT_RISK_SCORE"]}`
  - Output: per-metric `valid`, `errors`, and `warnings`.
- `GET /api/v1/metrics/lineage/{metric_code}`
  - Output: formula, dimensions, source tables, source fields, filters, aliases.
- `GET /api/v1/metrics/aliases`
  - Output: enabled metric alias mapping, optional `keyword` filter.
- `metric_catalog.aliases`
  - JSON column used for lightweight alias mapping.
- `config/metrics/catalog.yaml`
  - Expanded to 100 enabled metrics.

## Explicit Non-Goals

- No NL2SQL.
- No SQL generation or AST audit.
- No new semantic-layer tables beyond `metric_catalog.aliases`.
- No Milvus or Neo4j.
