<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api/client'
import ProjectRiskChart from '../components/ProjectRiskChart.vue'
import StatTile from '../components/StatTile.vue'
import RiskBadge from '../components/RiskBadge.vue'
import type { DashboardOverview } from '../types/api'

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

const overview = ref<DashboardOverview>(fallback)
const source = ref('加载中...')

onMounted(async () => {
  try {
    overview.value = await api.dashboard()
    source.value = '后端接口'
  } catch {
    source.value = '演示模式 (后端未连接)'
  }
})
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Dashboard / {{ source }}</p>
        <h2>安全风险驾驶舱</h2>
      </div>
    </div>

    <div class="stat-grid">
      <StatTile label="在建项目" :value="overview.total_projects" />
      <StatTile label="高风险项目" :value="overview.high_risk_projects" tone="danger" />
      <StatTile label="打开工单" :value="overview.open_work_orders" tone="warning" />
      <StatTile label="超期升级" :value="overview.overdue_work_orders" tone="danger" />
    </div>

    <section class="panel panel-wide">
      <div class="panel-head">
        <h3>项目风险排名</h3>
        <span>风险分越高，督办优先级越高</span>
      </div>
      <ProjectRiskChart v-if="overview.project_ranking.length > 0" :items="overview.project_ranking" />
      <p v-else style="padding:16px;color:var(--muted)">暂无项目风险数据</p>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>重点项目风险</h3>
      </div>
      <div class="list">
        <div v-for="item in overview.project_ranking.slice(0, 8)" :key="item.project_id" class="list-row">
          <div>
            <strong>{{ item.project_name }}</strong>
            <small>{{ item.project_id }}</small>
          </div>
          <div style="display:flex;gap:8px;align-items:center">
            <span style="font-weight:700;font-size:18px">{{ item.total_risk_score }}</span>
            <RiskBadge :level="item.risk_level" />
          </div>
        </div>
      </div>
    </section>

    <section class="panel">
      <div class="panel-head">
        <h3>最近规则触发</h3>
      </div>
      <div class="list">
        <div v-for="trigger in overview.recent_rule_triggers?.slice(0, 8)" :key="trigger.rule_id + trigger.created_at" class="list-row">
          <div>
            <strong>{{ trigger.rule_id }}</strong>
            <small>{{ trigger.object_type }}: {{ trigger.object_id }}</small>
          </div>
          <span class="status-chip" style="text-transform:uppercase">{{ trigger.severity }}</span>
        </div>
        <p v-if="!overview.recent_rule_triggers?.length" style="color:var(--muted)">暂无规则触发记录</p>
      </div>
    </section>
  </section>
</template>
