<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { api } from '../api/client'
import ProjectRiskChart from '../components/ProjectRiskChart.vue'
import StatTile from '../components/StatTile.vue'
import RiskBadge from '../components/RiskBadge.vue'
import { useScopeContext } from '../composables/useScopeContext'
import { dashboardCopyForUser, filterDashboardOverview } from '../scopeView'
import type { DashboardOverview, ScopeType } from '../types/api'

defineProps<{
  backendOnline?: boolean
}>()

const route = useRoute()
const { currentUser, projectFilter } = useScopeContext()

const fallback: DashboardOverview = {
  total_projects: 0,
  high_risk_projects: 0,
  critical_risk_projects: 0,
  open_work_orders: 0,
  overdue_work_orders: 0,
  high_risk_workers: 0,
  project_ranking: [],
  recent_rule_triggers: [],
}

const rawOverview = ref<DashboardOverview>(fallback)
const loading = ref(true)
const source = ref('加载中…')

const dashboardMode = computed(() => (route.meta.dashboardMode as ScopeType | undefined) ?? currentUser.value.scope_type)
const dashboardCopy = computed(() => dashboardCopyForUser(currentUser.value, dashboardMode.value))
const overview = computed(() => filterDashboardOverview(rawOverview.value, projectFilter.value))

async function loadOverview() {
  loading.value = true
  try {
    rawOverview.value = await api.dashboard()
    source.value = '实时数据'
  } catch {
    source.value = '演示模式'
  } finally {
    loading.value = false
  }
}

onMounted(loadOverview)
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Dashboard / {{ source }}</p>
        <h2>{{ dashboardCopy.title }}</h2>
      </div>
    </div>

    <div v-if="loading" class="stat-grid">
      <div v-for="n in 4" :key="n" class="stat-tile">
        <div class="loading-shimmer" style="width: 60%; margin-bottom: 12px" />
        <div class="loading-shimmer" style="width: 40%; height: 32px" />
      </div>
    </div>
    <div v-else class="stat-grid">
      <StatTile label="在建项目" :value="overview.total_projects" icon="folder" />
      <StatTile label="高风险项目" :value="overview.high_risk_projects" tone="danger" icon="alert" />
      <StatTile label="打开工单" :value="overview.open_work_orders" tone="warning" icon="clipboard" />
      <StatTile label="超期升级" :value="overview.overdue_work_orders" tone="danger" icon="trend" />
    </div>

    <section class="panel panel-wide">
      <div class="panel-head">
        <h3>{{ dashboardCopy.rankingTitle }}</h3>
        <span>{{ dashboardCopy.rankingHint }}</span>
      </div>
      <ProjectRiskChart v-if="overview.project_ranking.length > 0" :items="overview.project_ranking" />
      <div v-else class="loading-panel">
        {{ loading ? '加载项目风险数据…' : '暂无项目风险数据' }}
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>项目风险榜</h3>
        <span>Top 8</span>
      </div>
      <div class="list">
        <div v-for="item in overview.project_ranking.slice(0, 8)" :key="item.project_id" class="list-row">
          <div>
            <strong>{{ item.project_name }}</strong>
            <small>{{ item.project_id }}</small>
          </div>
          <div class="list-score">
            <span class="list-score-value">{{ item.total_risk_score }}</span>
            <RiskBadge :level="item.risk_level" />
          </div>
        </div>
        <p v-if="!loading && !overview.project_ranking.length" class="empty-state">暂无排名数据</p>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>最近规则触发</h3>
        <span>强规则优先</span>
      </div>
      <div class="list">
        <div
          v-for="trigger in overview.recent_rule_triggers?.slice(0, 8)"
          :key="trigger.rule_id + trigger.created_at"
          class="list-row"
        >
          <div>
            <strong>{{ trigger.rule_id }}</strong>
            <small>{{ trigger.object_type }} · {{ trigger.object_id }}</small>
          </div>
          <span class="status-chip status-overdue_escalated" style="text-transform: uppercase; font-size: 11px">
            {{ trigger.severity }}
          </span>
        </div>
        <p v-if="!loading && !overview.recent_rule_triggers?.length" class="empty-state">暂无规则触发记录</p>
      </div>
    </section>
  </section>
</template>
