# 14 Phase 2 Company-Project Scope Refactor Plan

## Goal

收敛当前组织域模型，只保留 **公司级 + 项目级** 两层权限边界。

目标模型：

```text
Company
  -> Project A
  -> Project B
  -> Project C
```

核心原则：

- 公司是租户边界。
- 项目是业务数据边界。
- 分包商、班组、工人、设备、隐患、工单是业务对象，不作为平台权限层级。
- 后端必须强制执行数据范围过滤，前端菜单隐藏不等于权限控制。
- Agent 和 NL2SQL 必须继承同一套公司/项目权限上下文。

## Scope

本计划只覆盖公司-项目两层组织域，不恢复集团/工程局/区域/项目/分包多级组织树。

In scope:

- 权限上下文从 `tenant_id + org_path + data_scope` 兼容迁移到 `company_id + project_id + scope_type + authorized_project_ids`。
- 后端统一 `apply_data_scope` 过滤策略。
- Mock 用户增加公司级、项目级样例。
- 主要读路径补公司/项目级权限测试。
- NL2SQL 审计注入从 `tenant_id/org_path` 转向 `company_id/project_id`。
- 前端按 `scope_type` 展示公司级或项目级视图。

Out of scope:

- 生产级 OAuth2/JWT/RBAC。
- 多级组织树、区域公司、工程局权限。
- 分包商/班组作为权限主体。
- 真实组织同步、SSO、通讯录集成。
- 直接开放 `/api/v1/agent/nl2sql`。

## Target Permission Context

公司级用户：

```json
{
  "user_id": "U001",
  "company_id": "C001",
  "scope_type": "company",
  "authorized_project_ids": ["P001", "P002", "P003"],
  "roles": ["company_admin", "company_safety_manager"]
}
```

项目级用户：

```json
{
  "user_id": "U101",
  "company_id": "C001",
  "scope_type": "project",
  "authorized_project_ids": ["P001"],
  "roles": ["project_manager", "project_safety_officer"]
}
```

Compatibility during migration:

```text
tenant_id  -> company_id
org_path   -> retained but not a primary filter
DataScope.TENANT -> scope_type = company
DataScope.ORG    -> scope_type = project
```

## Data Contract

### Project-Level Business Tables

Project-level business/fact tables should carry:

```sql
company_id VARCHAR(64) NOT NULL,
project_id VARCHAR(64) NOT NULL
```

Applicable table groups:

- Project/worker/subcontractor/equipment/hazard facts.
- Project/worker/subcontractor risk profiles.
- Work orders.
- Rule trigger logs.
- Agent task/audit records when they are project-scoped.

Recommended indexes:

```sql
INDEX idx_company_project (company_id, project_id)
INDEX idx_project_status (project_id, status)
```

### Company-Level Configuration Tables

Company-level configuration tables may allow nullable `project_id`:

```sql
company_id VARCHAR(64) NOT NULL,
project_id VARCHAR(64) NULL,
config_scope VARCHAR(32) NOT NULL
```

Meaning:

```text
project_id IS NULL -> company-level default config
project_id = P001  -> project-specific override
```

Applicable table groups:

- Rule configuration.
- Metric configuration.
- Prompt/config policy records.

## Migration Strategy

Do not rename or remove `tenant_id/org_path` in one step.

Recommended phases:

1. Add compatibility fields and user context.
2. Keep `tenant_id` populated with the same value as `company_id`.
3. Keep `org_path` nullable or retained for future expansion.
4. Update services to prefer `company_id/project_id` when available.
5. Update NL2SQL audit context and benchmark cases.
6. Remove hard dependency on `org_path` only after permission tests are green.

## Backend Scope Rules

Unified scope filter:

```python
def apply_data_scope(query, model, current_user):
    query = query.filter(model.company_id == current_user.company_id)

    if current_user.scope_type == "project":
        query = query.filter(model.project_id.in_(current_user.authorized_project_ids))

    return query
```

Path parameter guard:

```python
def assert_project_access(project_id, current_user):
    if current_user.scope_type == "project" and project_id not in current_user.authorized_project_ids:
        raise Forbidden("No permission to access this project")
```

Rules:

- Company users can read all projects under their company.
- Project users can read only authorized projects.
- URL/query/body `project_id` must never bypass backend scope checks.
- Company-level config with `project_id IS NULL` is visible to company users and applicable to projects.
- Project overrides are visible only within authorized project scope.

## API Strategy

Prefer unified APIs with backend scope filtering.

Keep business APIs project-aware:

```text
GET /api/v1/projects/{project_id}/profile
GET /api/v1/projects/{project_id}/workers
GET /api/v1/projects/{project_id}/hazards
GET /api/v1/projects/{project_id}/work-orders
```

Add a small number of company-level APIs when they represent a true aggregate:

```text
GET /api/v1/company/projects
GET /api/v1/company/risk-ranking
GET /api/v1/company/work-orders/overdue
GET /api/v1/company/subcontractors/ranking
```

Avoid duplicating every project API as a company API.

## Frontend Strategy

Use one frontend application and switch views based on `scope_type`.

Company view:

- Company dashboard.
- Project risk ranking.
- Project list/map.
- Cross-project hazard analysis.
- Cross-project subcontractor evaluation.
- Work-order supervision center.
- Company rule/metric configuration.
- Report center.

Project view:

- Project dashboard.
- Project profile.
- Project workers.
- Project subcontractors.
- Hazard rectification.
- Work orders.
- Rule trigger logs.
- AI assistant limited to authorized project data.

Project switcher:

- Company users: show `All projects / Project A / Project B`.
- Project users: hide switcher or show only the current project.

## Agent and NL2SQL Strategy

Agent context should include:

```json
{
  "company_id": "C001",
  "scope_type": "project",
  "authorized_project_ids": ["P001"],
  "forbidden_fields": ["id_card_no", "health_detail", "face_image_url", "raw_video_url"]
}
```

NL2SQL audit injection should change from:

```sql
tenant_id = :tenant_id
org_path LIKE :org_path
```

to:

Company scope:

```sql
company_id = :company_id
```

Project scope:

```sql
company_id = :company_id
AND project_id IN (:authorized_project_ids)
```

Rules:

- Candidate SQL remains untrusted.
- Scope injection remains mandatory.
- Project-level users must not receive cross-project rankings.
- If a project user asks a company-level question, the answer should be constrained to authorized project data or require clarification.

## Test Matrix

Minimum permission tests:

- Company user can see all projects in the same company.
- Company user cannot see another company.
- Project user can see authorized project.
- Project user cannot access another project by path parameter.
- Project user cannot access another project by query parameter.
- Dashboard results differ between company and project scope.
- Work-order list filters by company/project scope.
- Rule trigger logs filter by company/project scope.
- NL2SQL company scope injects only company filter.
- NL2SQL project scope injects company and project filters.
- NL2SQL rejects user-provided company/project override.
- Agent tool invocation receives authorized project list.

## Implementation Plan

### 14-A Design and Compatibility Layer

- Add this plan document.
- Define `ScopeType.COMPANY` and `ScopeType.PROJECT`.
- Extend `MockUser` with `company_id`, `scope_type`, and `authorized_project_ids`.
- Keep compatibility properties for `tenant_id`, `org_path`, and existing tests.

### 14-B Data Model Compatibility

- Add `company_id` to project-level tables where missing.
- Backfill `company_id = tenant_id`.
- Ensure project-scoped tables have `project_id` where business semantics require it.
- Add indexes for `(company_id, project_id)`.
- Keep `tenant_id/org_path` during transition.

### 14-C Backend Scope Enforcement

- Rewrite `apply_data_scope` to prefer company/project scope.
- Add path parameter access guard.
- Update dashboard, profiles, work orders, rules, metrics, cases, memory, and NL2SQL services.
- Add company/project mock headers or fixtures.

### 14-D NL2SQL Scope Refactor

- Update table/field whitelist to include `company_id` where needed.
- Change audit scope injection to company/project.
- Update 30 audit cases and 105 benchmark cases.
- Add cross-project vs project-only NL2SQL tests.

### 14-E Frontend View Split

- Fetch current user scope.
- Show company dashboard for company users.
- Show project dashboard for project users.
- Add project switcher for company users only.
- Hide unauthorized project/global views from project users.

### 14-F Acceptance Gate

- Backend pytest full green.
- Permission test matrix green.
- NL2SQL benchmark green after scope refactor.
- No API route exposes data without backend scope filtering.
- No direct dependency on `org_path` for core authorization.

## Risks

- Renaming `tenant_id` too early can break many existing tests and migrations.
- Some current tables may not have `project_id`; they need explicit classification as company-level or project-level.
- NL2SQL benchmark expected SQL fragments will need coordinated updates.
- Frontend may assume dashboard response shape is uniform; company/project views need clear contracts.

## Recommendation

Adopt the company-project model, but implement it as a compatibility migration:

```text
tenant_id as company_id first
project_id as project data boundary
org_path retained but de-emphasized
scope_type controls company/project behavior
```

This keeps the current Phase 2 work usable while making future Agent, NL2SQL, company dashboard, and project execution flows easier to reason about.

## Delivery Status

Completed on 2026-06-05:

- 14-A compatibility layer started.
- Added `ScopeType.COMPANY` and `ScopeType.PROJECT`.
- Extended `MockUser` with `company_id`, `scope_type`, and `authorized_project_ids`.
- Kept legacy `tenant_id`, `org_path`, and `DataScope` compatibility.
- Added mock auth headers `X-Company-Id`, `X-Scope-Type`, and `X-Authorized-Project-Ids`.
- Updated `apply_data_scope` to prefer company/project scope where available.
- Added `assert_project_access` helper for path/body project guards.
- Added company/project scope tests.
- Updated `/auth/me` mock contract test to verify new scope fields.
- Updated NL2SQL audit scope injection so project users with authorized projects receive `project_id IN (...)` injection instead of `org_path LIKE`.
- Added NL2SQL project override rejection for unauthorized `project_id`.
- 14-B data-model compatibility migration completed.
- Classified tenant-scoped tables requiring physical `company_id`: `project`, `subcontractor`, `worker`, `hazard`, `equipment`, `project_risk_profile`, `worker_risk_profile`, `subcontractor_risk_profile`, `rule_trigger_log`, `safety_work_order`, `agent_task_log`, `agent_nl2sql_audit`, `accident_case_library`, `agent_session_summary`, `agent_task_checkpoint`, and `profile_calc_detail`.
- Classified project-scoped tables requiring `project_id`: `project`, `worker`, `hazard`, `equipment`, `project_risk_profile`, `worker_risk_profile`, `subcontractor_risk_profile`, `rule_trigger_log`, `safety_work_order`, and `profile_calc_detail`.
- Kept `metric_catalog` as company-level configuration: `company_id NOT NULL`, `project_id NULL` for company defaults and project-specific overrides later.
- Added Alembic migration `backend/alembic/versions/20260605_0007_company_project_scope.py` to backfill `company_id = tenant_id` and add `(company_id, project_id)` indexes where useful.
- 14-D NL2SQL company/project scope conversion completed for the internal safety gate.
- NL2SQL table whitelist now includes physical `company_id` for company-scoped tables while keeping legacy `tenant_id/org_path` compatibility for old unsafe-input detection.
- Audit injection now prefers `company_id = current_user.company_id` and injects `project_id IN authorized_project_ids` for project-scope users.
- `metric_catalog` audit scope now keeps company defaults visible with `project_id IS NULL OR project_id IN (...)`.
- Prompt/schema context hides `company_id`, `tenant_id`, and `org_path` from the LLM while allowing business `project_id` fields.
- 105-case benchmark expectations were migrated from `tenant_id` fragments to `company_id` fragments.
- `/api/v1/agent/nl2sql` remains not exposed.

Not completed yet:

- Full service-by-service replacement of `tenant_id` with `company_id`.
- 14-E frontend company/project view split.

Verification:

- RED confirmed for company/project scope tests before implementation.
- RED confirmed for NL2SQL project-scope injection before implementation.
- `pytest tests/services/test_company_project_scope.py tests/services/test_data_scope.py tests/test_auth_mock.py -q`: 14 passed.
- `pytest tests/services/test_company_project_scope.py tests/services/test_data_scope.py tests/test_auth_mock.py tests/services/test_nl2sql_auditor.py tests/services/test_nl2sql_executor.py tests/services/test_nl2sql_prompt_builder.py tests/services/test_nl2sql_generator.py tests/services/test_nl2sql_qwen_provider.py tests/services/test_nl2sql_benchmark.py -q`: 43 passed.
- `pytest -q`: 97 passed.
- RED confirmed for `test_company_project_schema.py` before 14-B implementation.
- `alembic upgrade head`: upgraded `20260604_0006 -> 20260605_0007`.
- `python scripts/check_db_schema.py`: Schema check passed, 18 ORM tables match the database.
- `pytest tests/services/test_company_project_schema.py tests/services/test_company_project_scope.py tests/services/test_data_scope.py tests/test_auth_mock.py tests/services/test_nl2sql_auditor.py tests/services/test_nl2sql_benchmark.py tests/services/test_metrics.py -q`: 33 passed.
- `pytest -q`: 100 passed.
- RED confirmed for 14-D NL2SQL company/project scope tests before implementation.
- `pytest tests/services/test_nl2sql_auditor.py tests/services/test_nl2sql_prompt_builder.py tests/services/test_nl2sql_generator.py -q`: 19 passed.
- `pytest tests/services/test_nl2sql_benchmark.py -q`: 3 passed.
- `pytest tests/services/test_nl2sql_auditor.py tests/services/test_nl2sql_executor.py tests/services/test_nl2sql_prompt_builder.py tests/services/test_nl2sql_generator.py tests/services/test_nl2sql_qwen_provider.py tests/services/test_nl2sql_benchmark.py -q`: 31 passed.
- `pytest -q`: 102 passed.
