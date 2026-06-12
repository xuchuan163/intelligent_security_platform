import { createRouter, createWebHistory } from 'vue-router'

import { hasStoredSession, isJwtAuthMode } from '../auth/session'
import AgentApprovalsPage from '../pages/AgentApprovalsPage.vue'
import AttributionAnalysisPage from '../pages/AttributionAnalysisPage.vue'
import AssistantPage from '../pages/AssistantPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import DashboardRedirectPage from '../pages/DashboardRedirectPage.vue'
import HazardRectificationPage from '../pages/HazardRectificationPage.vue'
import Nl2SqlChatPage from '../pages/Nl2SqlChatPage.vue'
import MetricsCatalogPage from '../pages/MetricsCatalogPage.vue'
import ProjectProfilePage from '../pages/ProjectProfilePage.vue'
import ProjectReportPage from '../pages/ProjectReportPage.vue'
import SubcontractorReportPage from '../pages/SubcontractorReportPage.vue'
import RulesTriggersPage from '../pages/RulesTriggersPage.vue'
import SubcontractorProfilePage from '../pages/SubcontractorProfilePage.vue'
import WorkerProfilePage from '../pages/WorkerProfilePage.vue'
import LoginPage from '../pages/LoginPage.vue'
import WorkOrdersPage from '../pages/WorkOrdersPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginPage, meta: { layout: 'blank', public: true } },
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: DashboardRedirectPage },
    { path: '/dashboard/company', component: DashboardPage, meta: { dashboardMode: 'company' } },
    { path: '/dashboard/project', component: DashboardPage, meta: { dashboardMode: 'project' } },
    { path: '/profiles/projects', component: ProjectProfilePage },
    { path: '/reports/project', component: ProjectReportPage },
    { path: '/reports/subcontractor', component: SubcontractorReportPage },
    { path: '/profiles/workers', component: WorkerProfilePage },
    { path: '/profiles/subcontractors', component: SubcontractorProfilePage },
    { path: '/metrics', component: MetricsCatalogPage },
    { path: '/analysis/attribution', component: AttributionAnalysisPage },
    { path: '/rules/triggers', component: RulesTriggersPage },
    { path: '/work-orders', component: WorkOrdersPage },
    { path: '/agent/hazard-advisor', component: HazardRectificationPage },
    { path: '/agent/nl2sql', component: Nl2SqlChatPage },
    { path: '/agent/approvals', component: AgentApprovalsPage },
    { path: '/assistant', component: AssistantPage },
  ],
})

router.beforeEach((to) => {
  if (to.meta.public) {
    if (to.path === '/login' && hasStoredSession()) {
      return '/dashboard'
    }
    return true
  }
  if (isJwtAuthMode() && !hasStoredSession()) {
    return '/login'
  }
  return true
})

export default router
