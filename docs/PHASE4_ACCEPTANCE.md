# Phase 4 里程碑验收报告

**验收日期：** 2026-06-08  
**验收范围：** `docs/plans/09-phase4-algorithm-and-scale.md` §9 里程碑 + 质量门禁  
**验证环境：** Python 3.12.10、Windows 11、本机 MySQL:3306

---

## 1. 总览

| # | 里程碑 | 目标 | 结论 | 证据摘要 |
|:---:|---|---|---|---|
| 1 | 权重差异化 | 四类项目类型可切换且可回滚 | **通过** | 4-A `project_type_matrix.yaml` + `GET /config/weight-versions` |
| 2 | 案例回测 | 脚本可跑、报告可生成 | **通过** | `run_case_backtest.py` + `test_case_backtest.py` |
| 3 | 案例量 L2 | total ≥ 50 | **通过** | `AC-MVP-001` … `050` |
| 4 | 压测 500 | P95 达标 | **通过** | `docs/perf/baseline_500.md` |
| 5 | 压测 2000 | 目标规模报告 | **通过** | `docs/perf/baseline_2000.md` |
| 6 | 重算基线 | 批量耗时 + 连接池建议 | **通过** | `docs/perf/profile_recalculate_benchmark.md`、`DB_POOL_TUNING.md` |
| 7 | 贝叶斯 L2 | 专家先验可演示 | **通过** | `POST /api/v1/analysis/attribution` + `test_bayesian_l2.py` |
| 8 | 质量 | pytest 全绿 + schema + build | **通过** | **397 passed**；29 张 ORM 表对齐；`npm run build` 成功 |

**Phase 4 核心里程碑结论：通过** — 4-A/B/C/D 已交付，延后项（4-E behavior_memory、4-F 视频/BIM、4-G 灾备实操）未纳入本期门禁。

---

## 2. 自动化验证

### 2.1 Schema

```bash
cd backend
py -3.12 scripts/check_db_schema.py
```

**结果：** `Schema check passed: 29 ORM tables match the database.`

### 2.2 全量 pytest

```bash
cd backend
py -3.12 -m pytest -q
```

**结果：** `397 passed`（2026-06-08，72.96s）

**Phase 4 新增门禁子集：**

```bash
py -3.12 -m pytest \
  tests/services/test_case_backtest.py \
  tests/services/test_bayesian_l2.py \
  tests/services/test_seed_scale_data.py \
  tests/scripts/test_run_baseline_100.py \
  tests/scripts/test_run_baseline_500.py \
  tests/scripts/test_run_baseline_2000.py \
  tests/scripts/test_run_profile_recalculate_benchmark.py \
  -q
```

### 2.3 前端构建

```bash
cd frontend
npm run build
```

**结果：** `vue-tsc -b && vite build` 成功（5.23s）

---

## 3. 关键交付物索引

| 模块 | 文档/脚本 |
|---|---|
| 4-A 权重 | `config/weights/`、`GET /config/weight-versions` |
| 4-B 回测 | `backend/scripts/run_case_backtest.py` |
| 4-C 压测 | `backend/scripts/run_baseline_{100,500,2000}.py`、`run_profile_recalculate_benchmark.py` |
| 4-D 贝叶斯 | `backend/app/domain/bayesian/`、`POST /api/v1/analysis/attribution` |
| 性能报告 | `docs/perf/baseline_*.md`、`profile_recalculate_benchmark.md`、`DB_POOL_TUNING.md` |

---

## 4. 已知观察（非阻断）

- 2000 规模 `projects_list` P95 存在波动，全量列表建议分页/缓存（见 `baseline_2000.md`）。
- 租户级全量 `profile/recalculate` 耗时远超 30s SLA，建议改异步 Job（见 `profile_recalculate_benchmark.md`）。
- 压测 CLI 默认使用独立 `id_prefix`，避免与 `CSCEC-SCALE` 合成数据 ID 冲突。

---

## 5. 延后项（已永久关闭，见 `docs/PROJECT_CLOSURE.md`）

| 模块 | 原条件 | 收口处置 |
|---|---|---|
| 4-E behavior_memory | 合规评审签字 | 本期不再实施 |
| 4-F 视频 AI / BIM | 边缘/BIM 源接入 | 本期不再实施 |
| 4-G 灾备实操 | 准生产双活 | 本期不再实施 |
| 4-D L3 贝叶斯 | 案例 > 200 + 单独评审 | 本期不再实施 |
