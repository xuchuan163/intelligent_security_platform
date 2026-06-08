# 权重配置（Phase 4-A）

| 文件 | 用途 |
|---|---|
| `project_type_matrix.yaml` | 项目类型差异化系数（房建/市政/基建/机电） |
| `dynamic_factors.yaml` | 动态修正因子（DF-SCH / DF-WEA / DF-HZD） |

加载入口：

- `backend/app/domain/weights.py` → `load_project_type_matrix()`
- `backend/app/domain/dynamic_factors.py` → `load_dynamic_factor_config()`

变更须递增 `version` 并填写 `effective_from`；画像重算后生效。
