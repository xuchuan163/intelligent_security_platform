<script setup lang="ts">
import { CalendarDays, FileText } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import StatTile from '../components/StatTile.vue'
import { useScopeContext } from '../composables/useScopeContext'
import { ALL_PROJECTS_VALUE } from '../scopeView'
import type { ProjectWeeklyReport } from '../types/api'
import { statusLabel } from '../workOrderFlow'

const { availableProjects, projectFilter, selectedProjectId } = useScopeContext()

const projectId = ref('P001')
const weekEnd = ref('')
const report = ref<ProjectWeeklyReport | null>(null)
const loading = ref(true)
const loadError = ref('')

const projectOptions = computed(() =>
  availableProjects.value.map((project) => ({
    id: project.project_id,
    label: `${project.project_id} · ${project.project_name}`,
  })),
)

const kpi = computed(() => report.value?.kpi ?? null)
const periodLabel = computed(() => {
  if (!report.value) return ''
  const { start_date, end_date, week_label } = report.value.period
  return `${week_label} · ${start_date} 至 ${end_date}`
})

function syncProjectSelection() {
  if (projectFilter.value) {
    projectId.value = projectFilter.value
    return
  }
  if (projectOptions.value.length > 0) {
    projectId.value = projectOptions.value[0].id
  }
}

async function loadReport() {
  loading.value = true
  loadError.value = ''
  try {
    report.value = await api.projectWeeklyReport(projectId.value, weekEnd.value || undefined)
  } catch {
    loadError.value = '周报加载失败，请确认后端已启动且项目 ID 有效。'
    report.value = null
  } finally {
    loading.value = false
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 19)
}

function severityClass(severity: string): string {
  const map: Record<string, string> = {
    critical: 'status-overdue_escalated',
    high: 'status-waiting_review',
    medium: 'status-dispatched',
    low: 'status-closed',
  }
  return map[severity] ?? 'status-dispatched'
}

onMounted(() => {
  syncProjectSelection()
  loadReport()
})

watch(selectedProjectId, () => {
  if (selectedProjectId.value === ALL_PROJECTS_VALUE) {
    return
  }
  syncProjectSelection()
  loadReport()
})

watch(projectId, loadReport)
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Reports / Project Weekly</p>
        <h2>项目安全周报</h2>
      </div>
      <div class="report-toolbar">
        <label class="entity-switcher">
          <span>项目</span>
          <select v-model="projectId" :disabled="projectOptions.length <= 1">
            <option v-for="option in projectOptions" :key="option.id" :value="option.id">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="entity-switcher">
          <span>周截止日</span>
          <input v-model="weekEnd" type="date" @change="loadReport" />
        </label>
        <button type="button" class="action-button" :disabled="loading" @click="loadReport">刷新</button>
      </div>
    </div>

    <div v-if="loading" class="loading-panel">加载项目周报…</div>
    <p v-else-if="loadError" class="empty-state">{{ loadError }}</p>

    <template v-else-if="report">
      <section class="panel panel-wide profile-hero">
        <div>
          <p class="eyebrow">
            <FileText :size="14" />
            {{ report.report_id }}
          </p>
          <h3>{{ report.project_name }}</h3>
          <p class="profile-meta">
            <CalendarDays :size="14" />
            {{ periodLabel }} · 生成于 {{ formatTime(report.generated_at) }}
          </p>
        </div>
        <div v-if="kpi" class="profile-score">
          <span class="profile-score-value">{{ kpi.total_risk_score ?? '—' }}</span>
          <RiskBadge v-if="kpi.risk_level" :level="kpi.risk_level" />
          <span v-else class="status-chip status-dispatched">无画像</span>
        </div>
      </section>

      <div v-if="kpi" class="stat-grid">
        <StatTile label="未闭环隐患" :value="kpi.open_hazards" tone="warning" icon="alert" />
        <StatTile label="超期隐患" :value="kpi.overdue_hazards" tone="danger" icon="alert" />
        <StatTile label="在途工单" :value="kpi.open_work_orders" tone="warning" icon="clipboard" />
        <StatTile label="本周规则触发" :value="kpi.rule_triggers_count" tone="danger" icon="trend" />
        <StatTile label="高风险工人" :value="kpi.high_risk_workers" tone="warning" icon="folder" />
        <StatTile label="设备超期" :value="kpi.equipment_overdue_count" tone="danger" icon="alert" />
        <StatTile label="重大隐患未闭环" :value="kpi.major_hazards_open" tone="danger" icon="alert" />
        <StatTile label="本周新建工单" :value="kpi.week_new_work_orders" icon="clipboard" />
      </div>

      <section class="panel panel-wide">
        <div class="panel-head">
          <h3>周报要点</h3>
        </div>
        <ul class="highlight-list">
          <li v-for="(line, index) in report.highlights" :key="index">{{ line }}</li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>本周规则触发</h3>
          <span>{{ report.rule_triggers.length }} 条</span>
        </div>
        <div v-if="report.rule_triggers.length" class="list">
          <div v-for="item in report.rule_triggers" :key="item.trigger_id" class="list-row">
            <div>
              <strong>{{ item.rule_name }}</strong>
              <small>{{ item.rule_id }} · {{ item.object_type }} {{ item.object_id }}</small>
            </div>
            <span class="status-chip" :class="severityClass(item.severity)">{{ item.severity }}</span>
          </div>
        </div>
        <p v-else class="empty-state">本周暂无强规则触发</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>相关工单</h3>
          <span>{{ report.work_orders.length }} 条</span>
        </div>
        <div v-if="report.work_orders.length" class="list">
          <div v-for="order in report.work_orders" :key="order.work_order_id" class="list-row">
            <div>
              <strong>{{ order.title }}</strong>
              <small>{{ order.work_order_id }} · {{ order.work_order_type }}</small>
            </div>
            <span class="status-chip" :class="`status-${order.status}`">{{ statusLabel(order.status) }}</span>
          </div>
        </div>
        <p v-else class="empty-state">本周暂无相关工单</p>
      </section>
    </template>
  </section>
</template>

<style scoped>
.report-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px;
}

.report-toolbar input[type='date'] {
  min-width: 150px;
}

.highlight-list {
  margin: 0;
  padding-left: 1.25rem;
  display: grid;
  gap: 10px;
  color: var(--text);
  line-height: 1.55;
}

.profile-meta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
</style>
