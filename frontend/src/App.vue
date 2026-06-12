<script setup lang="ts">
import { computed, onMounted, provide, ref, type Component } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  Activity,
  BookOpen,
  MessageCircleQuestion,
  Bot,
  AlertTriangle,
  ClipboardCheck,
  ClipboardList,
  Database,
  FileText,
  GitBranch,
  HardHat,
  LayoutDashboard,
  RefreshCw,
  Shield,
  ShieldAlert,
  Users,
  Zap,
} from 'lucide-vue-next'

import { api } from './api/client'
import { clearAuthSession, getStoredAccessToken, hasStoredSession, isJwtAuthMode } from './auth/session'
import { startTokenRefreshLoop, stopTokenRefreshLoop } from './auth/tokenRefresh'
import { createScopeContext, SCOPE_CONTEXT_KEY } from './composables/useScopeContext'
import { useBackendHealth } from './composables/useBackendHealth'
import {
  fallbackCurrentUser,
  filterNavItemsForUser,
  projectSwitcherForUser,
  resolveNavTarget,
  topbarCopyForUser,
  type ScopeNavItem,
} from './scopeView'

interface AppNavItem extends ScopeNavItem {
  icon: Component
}

const navItems: AppNavItem[] = [
  { to: '/dashboard', label: '风险驾驶舱', icon: LayoutDashboard, scope: 'all', permission: 'dashboard.read' },
  { to: '/reports/project', label: '项目周报', icon: FileText, scope: 'all', permission: 'dashboard.read' },
  { to: '/reports/subcontractor', label: '分包评价', icon: Users, scope: 'all', permission: 'dashboard.read' },
  { to: '/profiles/projects', label: '项目画像', icon: ShieldAlert, scope: 'all', permission: 'profile.read' },
  { to: '/profiles/workers', label: '工人画像', icon: HardHat, scope: 'all', permission: 'profile.read' },
  { to: '/profiles/subcontractors', label: '分包商画像', icon: Users, scope: 'all', permission: 'profile.read' },
  { to: '/metrics', label: '指标目录', icon: BookOpen, scope: 'company', permission: 'metrics.read' },
  { to: '/analysis/attribution', label: '风险归因', icon: GitBranch, scope: 'company', permission: 'analysis.attribution' },
  { to: '/agent/nl2sql', label: '智能问数', icon: MessageCircleQuestion, scope: 'company', permission: 'agent.ask' },
  { to: '/rules/triggers', label: '规则日志', icon: Zap, scope: 'company', permission: 'rules.read' },
  { to: '/work-orders', label: '工单闭环', icon: ClipboardList, scope: 'all', permission: 'work_orders.read' },
  { to: '/agent/hazard-advisor', label: '隐患整改 Agent', icon: AlertTriangle, scope: 'all', permission: 'agent.ask' },
  { to: '/agent/approvals', label: 'Agent 审批', icon: ClipboardCheck, scope: 'company', permission: 'agent.approve' },
  { to: '/assistant', label: '安全助手', icon: Bot, scope: 'all', permission: 'agent.ask' },
]

const route = useRoute()
const router = useRouter()
const scopeContext = createScopeContext()
provide(SCOPE_CONTEXT_KEY, scopeContext)

const isBlankLayout = computed(() => route.meta.layout === 'blank')
const authSource = ref('加载用户上下文')
const { status: backendStatus, check: recheckBackend } = useBackendHealth()

const visibleNavItems = computed(() =>
  filterNavItemsForUser(navItems, scopeContext.currentUser.value).map((item) => ({
    ...item,
    to: resolveNavTarget(item, scopeContext.currentUser.value),
  })),
)
const topbarCopy = computed(() => topbarCopyForUser(scopeContext.currentUser.value))
const projectSwitcher = computed(() =>
  projectSwitcherForUser(
    scopeContext.currentUser.value,
    scopeContext.availableProjects.value,
    scopeContext.selectedProjectId.value,
  ),
)

const backendLabel = computed(() => {
  if (backendStatus.value === 'checking') return '检测后端…'
  if (backendStatus.value === 'online') return 'API 已连接'
  return 'API 未连接'
})

function onProjectChange(event: Event) {
  const target = event.target as HTMLSelectElement
  scopeContext.setSelectedProjectId(target.value)
}

async function bootstrapAuth() {
  const storedToken = getStoredAccessToken()
  if (storedToken) {
    api.setBearerToken(storedToken)
    try {
      await api.refreshSessionIfNeeded()
      const user = await api.me()
      await scopeContext.initializeFromAuth(user)
      authSource.value = user.auth_source === 'jwt' ? 'JWT Auth' : 'Session'
      startTokenRefreshLoop()
      return
    } catch {
      stopTokenRefreshLoop()
      clearAuthSession()
      api.logout()
    }
  }

  if (isJwtAuthMode()) {
    authSource.value = '未登录'
    await router.replace('/login')
    return
  }

  try {
    const user = await api.me()
    await scopeContext.initializeFromAuth(user)
    authSource.value = user.auth_source === 'jwt' ? 'JWT Auth' : 'Mock Auth'
  } catch {
    await scopeContext.initializeFromAuth(fallbackCurrentUser)
    authSource.value = '演示上下文'
  }
}

async function logout() {
  stopTokenRefreshLoop()
  api.logout()
  await scopeContext.initializeFromAuth(fallbackCurrentUser)
  authSource.value = '未登录'
  await router.replace('/login')
}

onMounted(async () => {
  if (!isBlankLayout.value) {
    await bootstrapAuth()
  }
})
</script>

<template>
  <RouterView v-if="isBlankLayout" />
  <div v-else class="app-shell">
    <aside class="sidebar">
      <div class="sidebar-glow" aria-hidden="true" />
      <div class="brand">
        <span class="brand-mark">
          <Shield :size="22" stroke-width="2.2" />
        </span>
        <div>
          <strong>中建智慧安全</strong>
          <small>工地安全智能管控平台</small>
        </div>
      </div>

      <nav>
        <RouterLink v-for="item in visibleNavItems" :key="item.to" :to="item.to">
          <component :is="item.icon" :size="18" stroke-width="2" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="sidebar-foot">
        <div class="backend-pill" :class="`backend-${backendStatus}`">
          <Activity :size="14" />
          <span>{{ backendLabel }}</span>
          <button type="button" class="pill-refresh" title="重新检测" @click="recheckBackend">
            <RefreshCw :size="13" :class="{ spinning: backendStatus === 'checking' }" />
          </button>
        </div>
        <p class="sidebar-note">强规则优先 · 画像可解释 · 工单可闭环</p>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div class="topbar-main">
          <span class="eyebrow">{{ topbarCopy.eyebrow }} / {{ authSource }}</span>
          <h1>{{ topbarCopy.title }}</h1>
        </div>
        <div class="topbar-status">
          <span class="status-pill user-pill">
            <span class="user-avatar">{{ scopeContext.currentUser.value.user_name.slice(0, 1) }}</span>
            {{ scopeContext.currentUser.value.user_name }}
          </span>
          <span class="status-pill">{{ topbarCopy.scopeLabel }}</span>
          <label v-if="projectSwitcher.visible" class="project-switcher">
            <span>项目</span>
            <select
              :value="projectSwitcher.selected"
              :disabled="projectSwitcher.readonly"
              @change="onProjectChange"
            >
              <option v-for="option in projectSwitcher.options" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <span class="status-pill muted-pill">
            <Database :size="13" />
            MySQL
          </span>
          <button
            v-if="hasStoredSession() || isJwtAuthMode()"
            type="button"
            class="action-button"
            @click="logout"
          >
            退出登录
          </button>
        </div>
      </header>

      <div v-if="backendStatus === 'offline'" class="connect-banner">
        <span>后端未响应。请运行 <code>python main.py</code> 或确认 Vite 代理目标（默认 <code>127.0.0.1:8011</code>）。</span>
        <button type="button" class="action-button action-primary" @click="recheckBackend">重试连接</button>
      </div>

      <RouterView v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" :backend-online="backendStatus === 'online'" />
        </transition>
      </RouterView>
    </main>
  </div>
</template>
