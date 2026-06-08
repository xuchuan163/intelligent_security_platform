# Rules Config

本目录承载 MVP 强规则 YAML 配置，已由后端运行时加载。

当前状态：

- `backend/app/services/rules/engine.py` 会读取 `*_rules.yaml`；
- 项目画像、工人画像、分包商画像计算已调用规则引擎；
- 三类画像重算时会将触发结果写入 `rule_trigger_log`；
- 规则 `action.auto_create_work_order=true` 时会自动生成未闭环工单，并按规则/对象去重；
- 规则配置保持轻量条件表达式，不做复杂 DSL。

当前文件：

- `project_rules.yaml`：项目强规则，包含 SR-PROJ-001、SR-PROJ-003、SR-PROJ-004；
- `subcontractor_rules.yaml`：分包商强规则，包含 SR-SUB-001、SR-SUB-002、SR-SUB-004；
- `worker_rules.yaml`：工人强规则，包含 SR-WORKER-001/002/004/005。

当前共 10 条强规则。历史事故类规则默认只计分、写日志，不自动创建工单。

新增规则时请保持字段命名与画像 facts 一致，并补充 `backend/tests/services/test_rule_engine.py`。

工单触发字段：

- `suggested_work_order_type`
- `work_order_title_template`
- `work_order_priority`
- `auto_create_work_order`
