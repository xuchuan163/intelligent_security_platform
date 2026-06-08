# 15 Phase 2 Frontend Company/Project View Plan

> This plan covers 14-E-A only. It adds the frontend scope context needed for company/project views, without a large page rebuild and without exposing `/api/v1/agent/nl2sql`.

## Goal

Use `/api/v1/auth/me` to drive frontend menu visibility, topbar labels, project switcher behavior, and dashboard wording for company-level and project-level users.

## Scope

In scope:

- Add a frontend `CurrentUser` contract matching `/auth/me`.
- Add `api.me()`.
- Add pure scope helpers for nav filtering, topbar labels, project switcher options, and dashboard copy.
- Update `App.vue` to load the current mock user once and drive nav/topbar from scope.
- Update `DashboardPage.vue` to receive the current scope and adjust page title/copy.
- Keep all backend data filtering in `apply_data_scope`; frontend scope only improves UX.

Out of scope:

- No new production authentication, JWT, or RBAC.
- No new company projects API.
- No full dashboard redesign.
- No separate company/project frontend applications.
- No `/api/v1/agent/nl2sql` route.

## Design

The frontend will keep one application shell. `App.vue` calls `api.me()` on mount and stores a `CurrentUser | null`. If `/auth/me` fails, the UI falls back to a company-level demo context so local static builds remain usable.

Navigation is defined as data and filtered by `scope_type`. Existing pages remain available in the first slice; future company-only pages can be added with `scope: "company"` and project-only pages with `scope: "project"`.

Project switcher behavior:

- Company user: show `全部项目` for now. A real project list can be added later through a company projects endpoint.
- Project user with one authorized project: show the project id as read-only context.
- Project user with multiple authorized projects: show only those authorized ids.

Dashboard behavior:

- Company user: title `公司安全风险驾驶舱`, ranking label `项目风险排名`.
- Project user: title `项目安全风险驾驶舱`, ranking label `授权项目风险概览`.
- The same `/dashboard/overview` API remains in use; backend scope filtering decides the actual data range.

## Files

- Modify `frontend/src/types/api.ts`: add `ScopeType`, `DataScope`, and `CurrentUser`.
- Modify `frontend/src/api/client.ts`: add `api.me()`.
- Create `frontend/src/scopeView.ts`: pure scope helper functions.
- Create `frontend/src/scopeView.test.ts`: pure TypeScript assertions for scope helpers.
- Modify `frontend/src/App.vue`: load current user and drive nav/topbar/project switcher context.
- Modify `frontend/src/pages/DashboardPage.vue`: accept `currentUser` prop and switch dashboard labels.
- Modify `docs/IMPLEMENTATION_ROADMAP.md`: record 14-E-A status.

## TDD Tasks

1. Write failing `scopeView.test.ts` for company/project nav, topbar, project switcher, and dashboard copy.
2. Implement `scopeView.ts` minimally.
3. Add `CurrentUser` type and `api.me()`.
4. Wire `App.vue` to `api.me()` and helper output.
5. Wire `DashboardPage.vue` label props.
6. Run frontend build and backend auth smoke.

## Acceptance

- Company user sees company topbar copy and all current MVP nav items.
- Project user sees project topbar copy and project-scoped context.
- Project switcher never shows unauthorized project ids.
- Dashboard wording changes by `scope_type`.
- `npm run build` succeeds.
- Backend `/auth/me` smoke test still passes.

## Delivery Status

Completed on 2026-06-05:

- Added `CurrentUser`, `ScopeType`, and `DataScope` frontend contracts.
- Added `api.me()` for `/api/v1/auth/me`.
- Added `frontend/src/scopeView.ts` pure helpers for nav filtering, topbar copy, project switcher state, and dashboard copy.
- Added `frontend/src/scopeView.test.ts` pure TypeScript assertions.
- Updated `App.vue` to load mock auth context, filter navigation, show company/project topbar copy, and render a scope-limited project switcher.
- Updated `DashboardPage.vue` to switch dashboard titles and ranking copy by `scope_type`.

Completed on 2026-06-03 (14-E-B):

- Added `GET /api/v1/projects` for scoped project list.
- Added `useScopeContext` composable with project switcher state and `projectFilter`.
- Split dashboard routes to `/dashboard/company` and `/dashboard/project` with `/dashboard` redirect.
- Wired project switcher-driven filtering on dashboard, work orders, rules triggers, and project profile pages.
- Applied nav permission matrix (`metrics`, `rules/triggers`, `agent/approvals` are company-only).

Verification:

- RED confirmed before implementation: `npm run build` failed on missing `CurrentUser` and missing `scopeView`.
- `esbuild src/scopeView.test.ts --bundle --platform=node --format=cjs --log-level=warning | node`: passed.
- `npm run build`: passed.
- `pytest tests/test_auth_mock.py -q`: 1 passed.
