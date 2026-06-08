# Phase 5 贝叶斯 L3 里程碑验收报告

**验收日期：** 2026-06-08  
**验收范围：** `docs/plans/10-bayesian-l3-implementation.md` L3-0 ~ L3-F  
**分支：** `feature/phase5-bayesian-l3`  
**验证环境：** Python 3.12.10、Windows、SQLite 单测 + 种子案例

---

## 1. 总览

| # | 里程碑 | 目标 | 结论 | 证据摘要 |
|:---:|---|---|---|---|
| 1 | 数据 | 活跃案例 ≥200 | **通过** | `seed_cases_l3_bulk.py`；`check_bayesian_l3_gate.py` |
| 2 | 结构 | DAG 可加载、无环 | **通过** | `test_bayesian_structure.py` |
| 3 | 训练 | CPT 可复现训练 + 版本文件 | **通过** | `train_bayesian_l3.py` → `cpt_learned.json` |
| 4 | 推理 | L3 归因含传播路径 | **通过** | `l3_inference.py`；`POST /analysis/attribution?model_level=L3` |
| 5 | 校准 | factor_hit_rate ≥ 0.55 | **通过** | `docs/algo/bayesian_l3_backtest.md`（81.12%） |
| 6 | 质量 | L3 pytest 子集全绿 | **通过** | 见 §2 |
| 7 | 合规 | `need_human_review: true` 全路径 | **通过** | L2/L3 服务与 API 测试断言 |

**Phase 5 L3 核心里程碑结论：通过**（L3-D/E/F 已交付；L4 与时序扩展未纳入）。

---

## 2. 自动化验证

```bash
cd backend
py -3.12 scripts/check_bayesian_l3_gate.py --tenant-id CSCEC  # 需先 seed_demo_data
py -3.12 scripts/train_bayesian_l3.py --from-seeds
py -3.12 scripts/run_bayesian_l3_backtest.py
py -3.12 -m pytest \
  tests/domain/test_bayesian_structure.py \
  tests/domain/test_bayesian_cpt.py \
  tests/services/test_bayesian_l3_labels.py \
  tests/services/test_bayesian_training.py \
  tests/services/test_bayesian_l3.py \
  tests/services/test_bayesian_l2.py \
  -q
```

---

## 3. API 演示

**L3 归因（auto 路由，需案例≥200 + CPT）：**

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analysis/attribution \
  -H "Content-Type: application/json" \
  -H "X-Tenant-Id: CSCEC" -H "X-Role: platform_admin" -H "X-Data-Scope: tenant" \
  -d '{"project_id":"P001","accident_type":"高处坠落","model_level":"L3"}'
```

**模型版本：**

```bash
curl http://127.0.0.1:8000/api/v1/config/bayesian-versions \
  -H "X-Tenant-Id: CSCEC" -H "X-Role: platform_admin" -H "X-Data-Scope: tenant"
```

---

## 4. 合规确认

| 项 | 状态 |
|---|---|
| L2/L3 输出 `need_human_review: true` | ✅ |
| 禁止作为处罚/清退/停工唯一依据（disclaimer） | ✅ |
| L3 训练仅用结构化案例字段 | ✅ |
| 案例扩充为脱敏合成描述 | ✅ |

---

## 5. 关键交付物

| 模块 | 路径 |
|---|---|
| DAG + 冷启动 | `config/bayesian/network_structure.yaml`、`cpt_prior.json` |
| 标注 + 训练集 | `case_labels.py`、`bayesian_l3_train_50.jsonl` |
| CPT 学习 | `training.py`、`cpt_learned.json` |
| L3 推理 | `l3_inference.py` |
| 路由 | `services/bayesian/service.py` |
| 版本 API | `GET /config/bayesian-versions` |
| 校准报告 | `docs/algo/bayesian_l3_backtest.md` |
