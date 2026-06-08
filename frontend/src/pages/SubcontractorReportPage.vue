<script setup lang="ts">
import { CalendarDays, ClipboardCheck, Users } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import StatTile from '../components/StatTile.vue'
import { useScopeContext } from '../composables/useScopeContext'
import { ALL_PROJECTS_VALUE } from '../scopeView'
import type { SubcontractorEvalReport } from '../types/api'
import { statusLabel } from '../workOrderFlow'

const subOptions = [
  { id: 'S001', label: 'S001 · 华东建设劳务' },
  { id: 'S002', label: 'S002 · 中建安装劳务' },
  { id: 'S003', label: 'S003 · 广东宏大建设' },
]

const dimensionLabels: Record<string, string> = {
  qualification_risk: '资质风险',
  worker_management: '工人管理',
  hazard_rectification: '隐患整改',
  violation_risk: '违规风险',
  equipment_management: '设备管理',
  accident_credit: '事故信用',
}

const { availableProjects, currentUser, projectFilter, selectedProjectId } = useScopeContext()

const subcontractorId = ref('S001')
const projectScope = ref('')
const evalDate = ref('')
const report = ref<SubcontractorEvalReport | null>(null)
const loading = ref(true)
const loadError = ref('')

const lockedSubcontractor = computed(() => currentUser.value.subcontractor_id ?? null)
const kpi = computed(() => report.value?.kpi ?? null)
const dimensionEntries = computed(() => {
  const scores = report.value?.profile.dimension_scores
  if (!scores) return []
  return Object.entries(scores).map(([key, value]) => ({
    key,
    label: dimensionLabels[key] ?? key,
    value: value ?? '—',
  }))
})

const projectScopeOptions = computed(() => [
  { id: '', label: '全部授权项目' },
  ...availableProjects.value.map((project) => ({
    id: project.project_id,
    label: `${project.project_id} · ${project.project_name}`,
  })),
])

function syncProjectScope() {
  projectScope.value = projectFilter.value ?? ''
}

function syncSubcontractorSelection() {
  if (lockedSubcontractor.value) {
    subcontractorId.value = lockedSubcontractor.value
  }
}

async function loadReport() {
  loading.value = true
  loadError.value = ''
  try {
    report.value = await api.subcontractorEvalReport(subcontractorId.value, {
      project_id: projectScope.value || undefined,
      eval_date: evalDate.value || undefined,
    })
  } catch {
    loadError.value = '分包商评价加载失败，请确认后端已启动且分包商 ID 有效。'
    report.value = null
  } finally {
    loading.value = false
  }
}

function formatTime(iso: string | null): string {
  if (!iso) return '—'
  return iso.replace('T', ' ').slice(0, 19)
}

function gradeClass(grade: string): string {
  const map: Record<string, string> = {
    优秀: 'status-closed',
    合格: 'status-dispatched',
    预警: 'status-waiting_review',
    不合格: 'status-overdue_escalated',
    待评估: 'status-pending_confirm',
  }
  return map[grade] ?? 'status-dispatched'
}

onMounted(() => {
  syncSubcontractorSelection()
  syncProjectScope()
  loadReport()
})

watch(selectedProjectId, () => {
  if (selectedProjectId.value === ALL_PROJECTS_VALUE) {
    projectScope.value = ''
  } else {
    syncProjectScope()
  }
  loadReport()
})

watch(subcontractorId, loadReport)
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Reports / Subcontractor Eval</p>
        <h2>分包商履约评价</h2>
      </div>
      <div class="report-toolbar">
        <label class="entity-switcher">
          <span>分包商</span>
          <select v-model="subcontractorId" :disabled="Boolean(lockedSubcontractor)">
            <option v-for="option in subOptions" :key="option.id" :value="option.id">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="entity-switcher">
          <span>项目范围</span>
          <select v-model="projectScope" @change="loadReport">
            <option v-for="option in projectScopeOptions" :key="option.id || 'all'" :value="option.id">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="entity-switcher">
          <span>评价日期</span>
          <input v-model="evalDate" type="date" @change="loadReport" />
        </label>
        <button type="button" class="action-button" :disabled="loading" @click="loadReport">刷新</button>
      </div>
    </div>

    <div v-if="loading" class="loading-panel">加载分包商评价…</div>
    <p v-else-if="loadError" class="empty-state">{{ loadError }}</p>

    <template v-else-if="report">
      <section class="panel panel-wide profile-hero">
        <div>
          <p class="eyebrow">
            <Users :size="14" />
            {{ report.report_id }}
          </p>
          <h3>{{ report.subcontractor_name }}</h3>
          <p class="profile-meta">
            <CalendarDays :size="14" />
            评价日 {{ report.eval_date }}
            <template v-if="report.project_name"> · {{ report.project_id }} {{ report.project_name }}</template>
            · 生成于 {{ formatTime(report.generated_at) }}
          </p>
        </div>
        <div class="profile-score">
          <span class="profile-score-value">{{ report.profile.total_risk_score ?? '—' }}</span>
          <RiskBadge v-if="report.profile.risk_level" :level="report.profile.risk_level" />
          <span class="status-chip" :class="gradeClass(report.profile.eval_grade)">
            {{ report.profile.eval_grade }}
          </span>
        </div>
      </section>

      <div v-if="kpi" class="stat-grid">
        <StatTile label="在场工人" :value="kpi.active_workers" icon="folder" />
        <StatTile label="高风险工人" :value="kpi.high_risk_workers" tone="warning" icon="alert" />
        <StatTile label="未闭环隐患" :value="kpi.open_hazards" tone="warning" icon="alert" />
        <StatTile label="超期隐患" :value="kpi.overdue_hazards" tone="danger" icon="alert" />
        <StatTile label="在途工单" :value="kpi.open_work_orders" tone="warning" icon="clipboard" />
        <StatTile label="30天违规" :value="kpi.violations_30d" tone="danger" icon="trend" />
        <StatTile label="历史事故" :value="kpi.accident_history_count" tone="danger" icon="alert" />
        <StatTile
          label="信用分"
          :value="kpi.credit_score != null ? kpi.credit_score.toFixed(0) : '—'"
          icon="folder"
        />
      </div>

      <section v-if="dimensionEntries.length" class="panel panel-wide">
        <div class="panel-head">
          <h3>维度得分</h3>
          <span v-if="report.profile.data_completeness != null">
            完整度 {{ Math.round(report.profile.data_completeness * 100) }}%
          </span>
        </div>
        <div class="dimension-grid">
          <div v-for="item in dimensionEntries" :key="item.key" class="dimension-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </section>

      <section v-if="report.profile.explanation" class="panel panel-wide">
        <div class="panel-head">
          <h3>画像解释</h3>
        </div>
        <p class="profile-copy">{{ report.profile.explanation }}</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>评价要点</h3>
        </div>
        <ul class="highlight-list">
          <li v-for="(line, index) in report.highlights" :key="`h-${index}`">{{ line }}</li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>
            <ClipboardCheck :size="16" />
            管理建议
          </h3>
        </div>
        <ul class="highlight-list">
          <li v-for="(line, index) in report.recommendations" :key="`r-${index}`">{{ line }}</li>
        </ul>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>未闭环隐患</h3>
          <span>{{ report.hazards.length }} 条</span>
        </div>
        <div v-if="report.hazards.length" class="list">
          <div v-for="hazard in report.hazards" :key="hazard.hazard_id" class="list-row">
            <div>
              <strong>{{ hazard.hazard_type }}</strong>
              <small>
                {{ hazard.hazard_id }} · {{ hazard.hazard_level }}
                <template v-if="hazard.is_major"> · 重大</template>
              </small>
            </div>
            <span class="status-chip" :class="`status-${hazard.status}`">{{ statusLabel(hazard.status) }}</span>
          </div>
        </div>
        <p v-else class="empty-state">暂无未闭环隐患</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>在途工单</h3>
          <span>{{ report.work_orders.length }} 条</span>
        </div>
        <div v-if="report.work_orders.length" class="list">
          <div v-for="order in report.work_orders" :key="order.work_order_id" class="list-row">
            <div>
              <strong>{{ order.title }}</strong>
              <small>{{ order.work_order_id }}</small>
            </div>
            <span class="status-chip" :class="`status-${order.status}`">{{ statusLabel(order.status) }}</span>
          </div>
        </div>
        <p v-else class="empty-state">暂无在途工单</p>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>重点关注工人</h3>
          <span>{{ report.workers_summary.length }} 人</span>
        </div>
        <div v-if="report.workers_summary.length" class="list">
          <div v-for="worker in report.workers_summary" :key="worker.worker_id" class="list-row">
            <div>
              <strong>{{ worker.worker_name_masked }}</strong>
              <small>{{ worker.worker_id }} · {{ worker.work_type }}</small>
            </div>
            <span class="status-chip status-waiting_review">违规 {{ worker.violation_count_30d }}</span>
          </div>
        </div>
        <p v-else class="empty-state">暂无工人摘要</p>
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
  flex-wrap: wrap;
}

.eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.dimension-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
}

.dimension-card {
  display: grid;
  gap: 6px;
  padding: 14px;
  border-radius: 12px;
  background: var(--panel-muted, rgba(255, 255, 255, 0.04));
  border: 1px solid var(--border);
}

.dimension-card span {
  color: var(--muted);
  font-size: 0.85rem;
}

.dimension-card strong {
  font-size: 1.35rem;
}
</style>
