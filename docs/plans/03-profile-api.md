# 03 Profile API Contract Plan

## Goal

画像 API 契约与技术文档对齐：`calculated_at` 对外暴露，低置信度 `confidence_level` 在 schema 中声明。

## Scope（Task 1.3.3 + 巩固 1.3.4）

- `backend/app/schemas/profiles.py`：`ProfileOut` 增加 `calculated_at`（映射 `calc_date` 或 `updated_at`）
- 三类 GET profile 响应均含 `confidence_level`
- 测试：API 或 service 层断言字段存在

## Out Of Scope

- 动态修正系数表（Phase 4）
- 按日历史快照表

## Steps

1. [ ] 写失败测试 `test_project_profile_includes_calculated_at_and_confidence`
2. [ ] 更新 `get_*_profile` 序列化
3. [ ] 更新 `frontend/src/types/api.ts`（如有类型）
4. [ ] `pytest -v`；勾选 1.3.3、1.3.4

## Acceptance

`GET /api/v1/profile/project/{id}` 的 `data` 含 `calculated_at`、`confidence_level`。
