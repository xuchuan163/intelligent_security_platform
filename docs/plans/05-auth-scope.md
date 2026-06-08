# 05 Auth Scope Completion Plan

## Goal

MVP 认证预留闭环：`tenant_id` / `data_scope` 覆盖主要读路径，权限测试 ≥ 10 条。

## Scope（Task 1.5.2 + 1.5.3）

- 已有：`security.py`、`profiles`、`work_orders` 部分 service
- 补齐：`dashboard`、`metrics`、`rules/triggers` 列表查询的 `apply_data_scope`（如适用）
- 测试：扩展 `test_data_scope.py` + `test_auth_mock.py` 至合计 ≥ 10 cases

## Out Of Scope

- JWT / OAuth2（Phase 3）
- 50+ 权限矩阵（Phase 2）

## Steps

1. [ ] 审计各 endpoint 是否注入 `current_user`
2. [ ] 写失败测试：越权租户/组织不可见数据
3. [ ] 实现过滤
4. [ ] `pytest -v tests/test_auth_mock.py tests/services/test_data_scope.py`
5. [ ] 勾选 1.5.2、1.5.3

## Note

`get_current_user` 位于 `app/core/security.py`（非 `core/auth.py`），文档以实际路径为准。
