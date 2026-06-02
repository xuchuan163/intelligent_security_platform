import { createRouter, createWebHistory } from 'vue-router'

import AssistantPage from '../pages/AssistantPage.vue'
import DashboardPage from '../pages/DashboardPage.vue'
import ProjectProfilePage from '../pages/ProjectProfilePage.vue'
import SubcontractorProfilePage from '../pages/SubcontractorProfilePage.vue'
import WorkerProfilePage from '../pages/WorkerProfilePage.vue'
import WorkOrdersPage from '../pages/WorkOrdersPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/dashboard' },
    { path: '/dashboard', component: DashboardPage },
    { path: '/profiles/projects', component: ProjectProfilePage },
    { path: '/profiles/workers', component: WorkerProfilePage },
    { path: '/profiles/subcontractors', component: SubcontractorProfilePage },
    { path: '/work-orders', component: WorkOrdersPage },
    { path: '/assistant', component: AssistantPage },
  ],
})

export default router
