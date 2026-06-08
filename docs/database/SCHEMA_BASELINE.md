# 数据库结构基线

当前数据库以 SQLAlchemy ORM 为事实来源，Alembic 迁移版本为 `20260602_0001`。

## 1. 连接信息

```text
host: 127.0.0.1
port: 3306
database: intelligent_security_platform
driver: mysql+pymysql
```

## 2. 当前核心表

| # | 表名 | 用途 |
|---:|---|---|
| 1 | tenant | 租户 |
| 2 | project | 项目主数据 |
| 3 | subcontractor | 分包商主数据 |
| 4 | worker | 工人主数据 |
| 5 | hazard | 隐患台账 |
| 6 | equipment | 设备台账 |
| 7 | project_risk_profile | 项目风险画像 |
| 8 | worker_risk_profile | 工人风险画像 |
| 9 | subcontractor_risk_profile | 分包商风险画像 |
| 10 | rule_trigger_log | 强规则触发日志 |
| 11 | safety_work_order | 安全工单 |
| 12 | agent_task_log | Agent 任务审计 |
| 13 | metric_catalog | 指标字典 |
| 14 | agent_task_checkpoint | Agent 任务 Checkpoint 预留 |
| 15 | profile_calc_detail | 画像计算明细 |

MySQL 中还会存在 Alembic 管理表 `alembic_version`。

## 3. 迁移规则

- 新表和字段必须先改 `backend/app/infrastructure/database/models.py`；
- 再创建或更新 Alembic migration；
- 禁止手工修改生产表结构后不记录迁移；
- 修改后运行：

```powershell
cd backend
$env:DATABASE_URL='mysql+pymysql://root:<password>@127.0.0.1:3306/intelligent_security_platform'
..\.venv\Scripts\alembic.exe upgrade head
..\.venv\Scripts\python.exe scripts\check_db_schema.py
```

## 4. 演示数据规模

| 表 | 当前 seed 数量 |
|---|---:|
| tenant | 1 |
| project | 3 |
| subcontractor | 3 |
| worker | 8 |
| hazard | 7 |
| equipment | 4 |
| safety_work_order | 5 |
| metric_catalog | 8 |

`seed_demo_data.py` 已做幂等处理，已有演示租户时会跳过。

## 5. 敏感数据要求

- 不存身份证号原文；
- 不存体检健康明细；
- 不存人脸原图或视频原始数据；
- 工人姓名只保留脱敏字段 `worker_name_masked`。

