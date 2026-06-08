import type { CurrentUser, DashboardOverview, ScopeType } from './types/api'

export type NavScope = ScopeType | 'all'

export const ALL_PROJECTS_VALUE = '__ALL__'
export const ALL_PROJECTS_LABEL = '全部项目'

export interface ScopeNavItem {
  to: string
  label: string
  scope: NavScope
  permission?: string
}

export interface TopbarCopy {
  eyebrow: string
  title: string
  scopeLabel: string
}

export interface DashboardCopy {
  title: string
  rankingTitle: string
  rankingHint: string
}

export interface ProjectListItem {
  project_id: string
  project_name: string
}

export interface ProjectSwitcherOption {
  value: string
  label: string
}

export interface ProjectSwitcherState {
  visible: boolean
  readonly: boolean
  selected: string
  options: ProjectSwitcherOption[]
}

export const fallbackCurrentUser: CurrentUser = {
  user_id: 'demo-company',
  user_name: 'Company Demo',
  tenant_id: 'CSCEC',
  company_id: 'CSCEC',
  org_path: 'CSCEC',
  role: 'company_admin',
  data_scope: 'tenant',
  scope_type: 'company',
  authorized_project_ids: [],
}

export function dashboardRouteForScope(scope: ScopeType | null | undefined): string {
  return scope === 'project' ? '/dashboard/project' : '/dashboard/company'
}

export function resolveNavTarget(item: ScopeNavItem, user: CurrentUser | null): string {
  if (item.to === '/dashboard') {
    return dashboardRouteForScope(user?.scope_type ?? fallbackCurrentUser.scope_type)
  }
  return item.to
}

export function filterNavItemsForUser<T extends ScopeNavItem>(items: T[], user: CurrentUser | null): T[] {
  const scope = user?.scope_type ?? fallbackCurrentUser.scope_type
  const scoped = items.filter((item) => item.scope === 'all' || item.scope === scope)
  const permissions = user?.permissions ?? []
  if (!permissions.length) {
    return scoped
  }
  return scoped.filter((item) => !item.permission || permissions.includes(item.permission))
}

export function topbarCopyForUser(user: CurrentUser | null): TopbarCopy {
  if ((user ?? fallbackCurrentUser).scope_type === 'project') {
    return {
      eyebrow: '项目级执行',
      title: '项目工地智慧安全平台',
      scopeLabel: '项目数据域',
    }
  }
  return {
    eyebrow: '公司级管控',
    title: '项目工地智慧安全平台',
    scopeLabel: '公司数据域',
  }
}

export function dashboardCopyForUser(user: CurrentUser | null, dashboardMode?: ScopeType | null): DashboardCopy {
  const scope = dashboardMode ?? user?.scope_type ?? fallbackCurrentUser.scope_type
  if (scope === 'project') {
    return {
      title: '项目安全风险驾驶舱',
      rankingTitle: '授权项目风险概览',
      rankingHint: '仅展示当前授权项目范围内的数据',
    }
  }
  return {
    title: '公司安全风险驾驶舱',
    rankingTitle: '项目风险排名',
    rankingHint: '风险分越高，督办优先级越高',
  }
}

export function projectFilterParam(selectedProjectId: string | null | undefined): string | undefined {
  if (!selectedProjectId || selectedProjectId === ALL_PROJECTS_VALUE) {
    return undefined
  }
  return selectedProjectId
}

export function initialSelectedProjectId(user: CurrentUser | null, projects: ProjectListItem[]): string {
  const currentUser = user ?? fallbackCurrentUser
  if (currentUser.scope_type === 'company') {
    return ALL_PROJECTS_VALUE
  }
  if (currentUser.authorized_project_ids.length > 0) {
    return currentUser.authorized_project_ids[0]
  }
  if (projects.length > 0) {
    return projects[0].project_id
  }
  return ALL_PROJECTS_VALUE
}

export function projectSwitcherForUser(
  user: CurrentUser | null,
  projects: ProjectListItem[] = [],
  selectedProjectId: string | null = null,
): ProjectSwitcherState {
  const currentUser = user ?? fallbackCurrentUser
  const selected = selectedProjectId ?? initialSelectedProjectId(currentUser, projects)

  if (currentUser.scope_type === 'company') {
    const options: ProjectSwitcherOption[] = [
      { value: ALL_PROJECTS_VALUE, label: ALL_PROJECTS_LABEL },
      ...projects.map((project) => ({
        value: project.project_id,
        label: `${project.project_id} · ${project.project_name}`,
      })),
    ]
    return {
      visible: true,
      readonly: false,
      selected,
      options,
    }
  }

  const authorized = new Set(currentUser.authorized_project_ids)
  const scopedProjects =
    authorized.size > 0 ? projects.filter((project) => authorized.has(project.project_id)) : projects

  if (scopedProjects.length === 0 && currentUser.authorized_project_ids.length > 0) {
    const fallbackOptions = currentUser.authorized_project_ids.map((projectId) => ({
      value: projectId,
      label: projectId,
    }))
    return {
      visible: true,
      readonly: fallbackOptions.length <= 1,
      selected: fallbackOptions.some((option) => option.value === selected) ? selected : fallbackOptions[0].value,
      options: fallbackOptions,
    }
  }

  const options =
    scopedProjects.length > 0
      ? scopedProjects.map((project) => ({
          value: project.project_id,
          label: `${project.project_id} · ${project.project_name}`,
        }))
      : [{ value: ALL_PROJECTS_VALUE, label: '未绑定项目' }]

  return {
    visible: true,
    readonly: options.length <= 1,
    selected: options.some((option) => option.value === selected) ? selected : options[0].value,
    options,
  }
}

export function filterDashboardOverview(
  overview: DashboardOverview,
  projectId: string | undefined,
): DashboardOverview {
  if (!projectId) {
    return overview
  }

  const projectRanking = overview.project_ranking.filter((item) => item.project_id === projectId)
  const recentRuleTriggers = overview.recent_rule_triggers?.filter((item) => item.project_id === projectId)

  return {
    ...overview,
    total_projects: projectRanking.length > 0 ? 1 : 0,
    high_risk_projects: projectRanking.filter((item) => item.risk_level === 'high' || item.risk_level === 'critical')
      .length,
    critical_risk_projects: projectRanking.filter((item) => item.risk_level === 'critical').length,
    project_ranking: projectRanking,
    recent_rule_triggers: recentRuleTriggers,
  }
}
