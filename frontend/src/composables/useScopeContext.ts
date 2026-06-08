import { computed, inject, ref, type ComputedRef, type InjectionKey, type Ref } from 'vue'

import { api } from '../api/client'
import {
  ALL_PROJECTS_VALUE,
  fallbackCurrentUser,
  initialSelectedProjectId,
  projectFilterParam,
  type ProjectListItem,
} from '../scopeView'
import type { CurrentUser } from '../types/api'

export interface ScopeContext {
  currentUser: Ref<CurrentUser>
  selectedProjectId: Ref<string>
  projectFilter: ComputedRef<string | undefined>
  availableProjects: Ref<ProjectListItem[]>
  setSelectedProjectId: (projectId: string) => void
  reloadProjects: () => Promise<void>
  initializeFromAuth: (user: CurrentUser) => Promise<void>
}

export const SCOPE_CONTEXT_KEY: InjectionKey<ScopeContext> = Symbol('scopeContext')

export function syncMockAuthFromUser(user: CurrentUser): void {
  if (user.auth_source === 'jwt') {
    api.clearMockAuthContext()
    return
  }
  api.setMockAuthContext({
    userId: user.user_id,
    userName: user.user_name,
    role: user.role,
    tenantId: user.tenant_id,
    companyId: user.company_id,
    orgPath: user.org_path,
    scopeType: user.scope_type,
    dataScope: user.data_scope,
    authorizedProjectIds: user.authorized_project_ids,
  })
}

export function createScopeContext(): ScopeContext {
  const currentUser = ref<CurrentUser>(fallbackCurrentUser)
  const availableProjects = ref<ProjectListItem[]>([])
  const selectedProjectId = ref<string>(ALL_PROJECTS_VALUE)

  const projectFilter = computed(() => projectFilterParam(selectedProjectId.value))

  async function reloadProjects() {
    try {
      const response = await api.projects()
      availableProjects.value = response.items
    } catch {
      availableProjects.value = []
    }
  }

  function setSelectedProjectId(projectId: string) {
    selectedProjectId.value = projectId
  }

  async function initializeFromAuth(user: CurrentUser) {
    currentUser.value = user
    syncMockAuthFromUser(user)
    await reloadProjects()
    selectedProjectId.value = initialSelectedProjectId(user, availableProjects.value)
  }

  return {
    currentUser,
    selectedProjectId,
    projectFilter,
    availableProjects,
    setSelectedProjectId,
    reloadProjects,
    initializeFromAuth,
  }
}

export function useScopeContext(): ScopeContext {
  const context = inject(SCOPE_CONTEXT_KEY)
  if (!context) {
    throw new Error('Scope context is not available')
  }
  return context
}
