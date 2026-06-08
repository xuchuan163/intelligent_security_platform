import type { CurrentUser } from './types/api'
import {
  ALL_PROJECTS_LABEL,
  ALL_PROJECTS_VALUE,
  dashboardCopyForUser,
  dashboardRouteForScope,
  fallbackCurrentUser,
  filterDashboardOverview,
  filterNavItemsForUser,
  initialSelectedProjectId,
  projectFilterParam,
  projectSwitcherForUser,
  resolveNavTarget,
  topbarCopyForUser,
  type ScopeNavItem,
} from './scopeView'

function assertEqual<T>(actual: T, expected: T, message: string) {
  if (actual !== expected) {
    throw new Error(`${message}: expected ${String(expected)}, got ${String(actual)}`)
  }
}

function assertDeepEqual<T>(actual: T, expected: T, message: string) {
  const actualJson = JSON.stringify(actual)
  const expectedJson = JSON.stringify(expected)
  if (actualJson !== expectedJson) {
    throw new Error(`${message}: expected ${expectedJson}, got ${actualJson}`)
  }
}

const navItems: ScopeNavItem[] = [
  { to: '/dashboard', label: '驾驶舱', scope: 'all' },
  { to: '/company/reports', label: '公司报告', scope: 'company' },
  { to: '/project/tasks', label: '项目任务', scope: 'project' },
  { to: '/metrics', label: '指标目录', scope: 'company' },
]

const companyUser: CurrentUser = {
  user_id: 'u-company',
  user_name: 'Company User',
  tenant_id: 'COMPANY-A',
  company_id: 'COMPANY-A',
  org_path: 'COMPANY-A',
  role: 'company_admin',
  data_scope: 'tenant',
  scope_type: 'company',
  authorized_project_ids: ['P001', 'P002'],
}

const projectUser: CurrentUser = {
  user_id: 'u-project',
  user_name: 'Project User',
  tenant_id: 'COMPANY-A',
  company_id: 'COMPANY-A',
  org_path: 'COMPANY-A/P001',
  role: 'project_manager',
  data_scope: 'org',
  scope_type: 'project',
  authorized_project_ids: ['P001'],
}

const projects = [
  { project_id: 'P001', project_name: '临港 TOD' },
  { project_id: 'P002', project_name: '武汉中心' },
]

assertDeepEqual(
  filterNavItemsForUser(navItems, companyUser).map((item) => item.to),
  ['/dashboard', '/company/reports', '/metrics'],
  'company nav filters project-only items',
)
assertDeepEqual(
  filterNavItemsForUser(navItems, projectUser).map((item) => item.to),
  ['/dashboard', '/project/tasks'],
  'project nav filters company-only items',
)

assertEqual(resolveNavTarget({ to: '/dashboard', label: '驾驶舱', scope: 'all' }, companyUser), '/dashboard/company', 'company dashboard route')
assertEqual(resolveNavTarget({ to: '/dashboard', label: '驾驶舱', scope: 'all' }, projectUser), '/dashboard/project', 'project dashboard route')
assertEqual(dashboardRouteForScope('company'), '/dashboard/company', 'company dashboard path')
assertEqual(dashboardRouteForScope('project'), '/dashboard/project', 'project dashboard path')

assertEqual(topbarCopyForUser(companyUser).eyebrow, '公司级管控', 'company topbar eyebrow')
assertEqual(topbarCopyForUser(projectUser).eyebrow, '项目级执行', 'project topbar eyebrow')

assertEqual(dashboardCopyForUser(companyUser).title, '公司安全风险驾驶舱', 'company dashboard title')
assertEqual(dashboardCopyForUser(projectUser).rankingTitle, '授权项目风险概览', 'project ranking title')
assertEqual(dashboardCopyForUser(companyUser, 'project').title, '项目安全风险驾驶舱', 'dashboard mode override')

assertEqual(initialSelectedProjectId(companyUser, projects), ALL_PROJECTS_VALUE, 'company default selection')
assertEqual(initialSelectedProjectId(projectUser, projects), 'P001', 'project default selection')
assertEqual(projectFilterParam(ALL_PROJECTS_VALUE), undefined, 'all projects has no filter')
assertEqual(projectFilterParam('P002'), 'P002', 'project filter param')

const companySwitcher = projectSwitcherForUser(companyUser, projects, ALL_PROJECTS_VALUE)
assertEqual(companySwitcher.readonly, false, 'company switcher interactive')
assertEqual(companySwitcher.options[0].label, ALL_PROJECTS_LABEL, 'company switcher all option')
assertEqual(companySwitcher.options.length, 3, 'company switcher includes projects')

const projectSwitcher = projectSwitcherForUser(projectUser, projects, 'P001')
assertEqual(projectSwitcher.readonly, true, 'single project switcher readonly')
assertDeepEqual(
  projectSwitcher.options.map((option) => option.value),
  ['P001'],
  'project switcher only authorized ids',
)

const filteredOverview = filterDashboardOverview(
  {
    total_projects: 3,
    high_risk_projects: 2,
    open_work_orders: 5,
    overdue_work_orders: 1,
    project_ranking: [
      { project_id: 'P001', project_name: 'A', total_risk_score: 80, risk_level: 'high' },
      { project_id: 'P002', project_name: 'B', total_risk_score: 40, risk_level: 'medium' },
    ],
    recent_rule_triggers: [
      {
        rule_id: 'SR-001',
        object_type: 'project',
        object_id: 'P001',
        project_id: 'P001',
        severity: 'high',
        created_at: '2026-06-03T10:00:00+08:00',
      },
      {
        rule_id: 'SR-002',
        object_type: 'project',
        object_id: 'P002',
        project_id: 'P002',
        severity: 'medium',
        created_at: '2026-06-03T11:00:00+08:00',
      },
    ],
  },
  'P001',
)

assertEqual(filteredOverview.total_projects, 1, 'dashboard filter narrows project count')
assertEqual(filteredOverview.project_ranking.length, 1, 'dashboard filter narrows ranking')
assertEqual(filteredOverview.recent_rule_triggers?.length, 1, 'dashboard filter narrows triggers')

assertEqual(fallbackCurrentUser.scope_type, 'company', 'fallback user is company scoped')

const permissionNavItems: ScopeNavItem[] = [
  { to: '/dashboard', label: '驾驶舱', scope: 'all', permission: 'dashboard.read' },
  { to: '/metrics', label: '指标目录', scope: 'company', permission: 'metrics.read' },
  { to: '/agent/approvals', label: '审批', scope: 'company', permission: 'agent.approve' },
]

const projectOfficer: CurrentUser = {
  ...projectUser,
  permissions: ['dashboard.read', 'profile.read', 'work_orders.read', 'agent.ask'],
}

assertDeepEqual(
  filterNavItemsForUser(permissionNavItems, projectOfficer).map((item) => item.to),
  ['/dashboard'],
  'permission filter hides metrics and approvals for project officer',
)
