# 01 Metric Semantic Layer Plan

## Goal

将指标目录从 8 条扩展到 **30 条**，配置与 DB 一致，供驾驶舱、画像解释与后续 NL2SQL 使用。

## Scope（Task 1.2.2 + 1.2.3）

- 新增 `config/metrics/catalog.yaml`（≥30 条，对齐技术文档附录 A 核心指标）
- 扩展 `backend/scripts/seed_demo_data.py` 或独立 `scripts/seed_metrics.py` 从 YAML 灌库
- 新增 `backend/tests/services/test_metrics.py`（列表分页、详情 404、seed 数量）
- 保持 `GET /api/v1/metrics/catalog`、`GET /api/v1/metrics/{code}` 行为不变

## Out Of Scope

- POST validate、lineage、aliases（Phase 2 Task 2.2.x）
- 前端指标页（Task 1.2.5，Sprint E 可选）

## Files

| 操作 | 路径 |
|---|---|
| Create | `config/metrics/catalog.yaml` |
| Modify | `backend/scripts/seed_demo_data.py` |
| Create | `backend/tests/services/test_metrics.py` |
| Read | `backend/app/services/metrics/service.py` |

## Steps

1. [x] 从附录 A + 现有 8 条补全 30 条 YAML（含 `metric_code`、`metric_name`、`business_definition`、`status`）
2. [x] 写失败测试：`test_metric_catalog_has_at_least_30_active_metrics`
3. [x] seed 脚本读 YAML 写入 `metric_catalog`（幂等：按 code upsert）
4. [x] `pytest -v tests/services/test_metrics.py`
5. [x] 勾选路线图 1.2.2、1.2.3

## Acceptance

```bash
curl "http://127.0.0.1:8000/api/v1/metrics/catalog?page_no=1&page_size=50"
# data.total >= 30
```
