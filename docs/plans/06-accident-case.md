# 06 Accident Case Library MVP Plan

## Goal

MVP 事故案例库：表 + 5 条种子 + `GET /api/v1/case/list`（Task 1.6.1–1.6.3）。

## Scope

- Alembic：`accident_case_library` 表（对齐 `技术参考文档/数据库数据表设计文档.md` §4.7 核心字段）
- Model + `schemas/cases.py` + `services/cases/service.py` + `endpoints/cases.py`
- seed 5 条结构化案例（无身份证、无敏感明细原文）
- 测试：列表 API、tenant 过滤

## Out Of Scope

- Milvus 向量、案例详情 RAG（Phase 3）
- 贝叶斯回测（Phase 4）

## Steps

1. [ ] models.py → alembic revision → upgrade
2. [ ] 失败测试 `test_case_list_returns_seeded_cases`
3. [ ] seed + endpoint + router 注册
4. [ ] `pytest -v`；勾选 1.6.x

## Acceptance

`GET /api/v1/case/list` 返回 `code=SUCCESS`，`data.items.length >= 5`。
