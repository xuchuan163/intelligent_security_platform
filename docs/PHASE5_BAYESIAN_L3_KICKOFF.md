# Phase 5 贝叶斯 L3 专项评审纪要

| 项 | 内容 |
|---|---|
| 会议目标 | 确认 L3 重新立项范围、数据门禁、合规红线与 Sprint 排期 |
| 日期 | 2026-06-08 |
| 分支 | `feature/phase5-bayesian-l3` |
| 材料 | `docs/PHASE4_ACCEPTANCE.md`、`docs/plans/10-bayesian-l3-implementation.md`、`AGENTS.md` §5.4 |

---

## 1. 重新立项背景

Phase 0–4 已验收收口（`docs/PROJECT_CLOSURE.md`）。现**单独立项 Phase 5：贝叶斯 L3**，在 L2 专家先验基础上引入 DAG + CPT 参数学习，不替代既有画像与工单闭环。

**Phase 4 复盘结论：** L2 `POST /api/v1/analysis/attribution` 已交付；案例库 50 条满足 L2，**未达 L3 门槛 200 条**。

---

## 2. 范围确认

| 子阶段 | 内容 | 表决 |
|:---:|---|:---:|
| L3-0 | 启动门禁 + 案例质检脚本 | ✅ 批准 |
| L3-A | DAG 结构 + CPT 槽位 + 冷启动先验 | ✅ 批准 |
| L3-B | 案例因子标注 + 训练集 + 扩至 200 条 | ✅ 批准 |
| L3-C | CPT 训练 + 校准回测 | ⬜ Sprint 2 |
| L3-D | L3 推理 + L2 回退 | ⬜ Sprint 3 |
| L3-E | API 扩展 + 版本查询 | ⬜ Sprint 3 |
| L3-F | 验收报告 + pytest 全量 | ⬜ Sprint 3 |

**明确不做（本期 L3 范围内）：**

- 贝叶斯 L4（时序/GNN）
- 在线自动重训 cron
- L3 结论驱动自动处罚/清退/停工工单
- behavior_memory、视频 AI、BIM、灾备实操

---

## 3. 数据门禁

| 级别 | 案例量 | 本期动作 |
|---|---:|---|
| L2（已交付） | 50–200 | 保持 `model_level` 默认 L2 |
| **L3（本期）** | **≥ 200** | `check_bayesian_l3_gate.py` 通过后方可训练/上线 L3 |

**Sprint 1 策略：** 允许在 <200 时完成 L3-A/L3-B 代码与黄金集 TDD；**L3-C 训练与 L3-D 上线**须门禁通过。

---

## 4. 合规红线（全票通过，不可放宽）

| 项 | 规则 |
|---|---|
| 归因输出 | 不得作为处罚、清退、停工的**唯一**依据 |
| 人工复核 | L3 API 全路径 `need_human_review: true` |
| 训练数据 | 仅使用结构化案例字段；不向在线 LLM 传入敏感原文 |
| 压测/合成 | 扩案例脚本仅生成脱敏合成描述，禁止生产库直拉 |

---

## 5. 首 Sprint 任务（L3-0 → L3-A → L3-B）

| Task | 交付 |
|---|---|
| L3-0.1–0.3 | 门禁脚本、覆盖报告、本纪要 |
| L3-A.1–A.4 | `network_structure.yaml`、`structure.py`、`cpt.py`、`cpt_prior.json` |
| L3-B.1–B.6 | `case_labels.py`、`dataset.py`、黄金集、案例 200+ 种子 |

**编码入口：** `docs/plans/10-bayesian-l3-implementation.md`

---

## 6. 表决签字（勾选）

- [x] 批准 **Phase 5 L3 重新立项**，解除 `PROJECT_CLOSURE.md` 中 L3 冻结
- [x] 批准分支 **`feature/phase5-bayesian-l3`**
- [x] 确认合规红线（§4）对 L3 全路径生效
- [x] 批准 Sprint 1：**L3-0 + L3-A + L3-B**
- [x] L3-C/D/E/F 待 Sprint 1 验收后再开工

---

**维护：** Sprint 结束时更新 `docs/plans/10-bayesian-l3-implementation.md` Task 勾选与 `IMPLEMENTATION_ROADMAP.md` Phase 5 进度。
