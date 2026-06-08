# 枚举与常量基线

本文档记录当前 MVP 代码中已经使用的关键枚举、状态和业务常量。修改这些值会影响接口、数据库和前端展示。

## 1. 风险等级

| risk_level | 分值范围 | 说明 |
|---|---:|---|
| low | 0-30 | 低风险 |
| medium | 31-60 | 中风险 |
| high | 61-80 | 高风险 |
| critical | 81-100 | 极高风险 |

来源：`backend/app/domain/risk.py`

## 2. 工单状态

| 状态 | 说明 |
|---|---|
| pending_confirm | 待确认 |
| dispatched | 已派发 |
| processing | 处理中 |
| waiting_review | 待复查 |
| closed | 已关闭 |
| rejected | 已驳回 |
| overdue_escalated | 超期升级 |

合法流转：

| 当前状态 | action | 目标状态 |
|---|---|---|
| pending_confirm | confirm | dispatched |
| dispatched | accept | processing |
| processing | submit_result | waiting_review |
| waiting_review | review_pass | closed |
| waiting_review | review_reject | processing |
| processing | timeout | overdue_escalated |

来源：`backend/app/domain/work_orders.py`

## 3. 工单类型

| work_order_type | 说明 |
|---|---|
| rectification | 隐患整改 |
| equipment_inspection | 设备核查 |
| worker_training | 工人培训复训 |
| risk_warning | 风险预警 |
| subcontractor_interview | 分包约谈 |
| operation_restriction | 作业限制 |
| emergency_rectification | 应急整改 |

## 4. 核心强规则

| rule_id | 说明 | 当前来源 |
|---|---|---|
| SR-PROJ-001 | 重大隐患超期未闭环 | 项目画像计算/seed |
| SR-PROJ-004 | 特种设备超期未检仍使用 | 项目画像计算/seed |
| SR-WORKER-001 | 特种作业证异常 | 工人画像计算 |
| SR-WORKER-005 | 频繁违规 | 工人画像计算 |

P1 计划将强规则迁移到 `config/rules/*.yaml`。

## 5. API 错误码

| HTTP | code | 说明 |
|---:|---|---|
| 400 | 40001 | 参数或业务请求错误 |
| 404 | 40401 | 资源不存在 |
| 409 | 40901 | 状态冲突，如非法工单流转 |
| 422 | 42201 | 请求体验证失败 |
| 500 | 50001 | 系统内部错误 |
| 503 | 50301 | 数据库或上游不可用 |

来源：`backend/app/core/errors.py`

## 6. 固定演示租户

| 常量 | 值 |
|---|---|
| tenant_id | CSCEC |
| database | intelligent_security_platform |
| backend port | 8000 |
| frontend port | 5173 |

