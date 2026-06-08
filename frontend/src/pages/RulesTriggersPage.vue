<script setup lang="ts">
import { AlertOctagon, Filter, Zap } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import { useScopeContext } from '../composables/useScopeContext'
import { ALL_PROJECTS_VALUE } from '../scopeView'
import { STRONG_RULE_OPTIONS } from '../strongRules'
import type { RuleTriggerLog } from '../types/api'

const { availableProjects, projectFilter, selectedProjectId } = useScopeContext()

const triggers = ref<RuleTriggerLog[]>([])
const selected = ref<RuleTriggerLog | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const severityFilter = ref('')
const projectIdFilter = ref('')
const ruleIdFilter = ref('')

const projectOptions = computed(() => [
  { id: '', label: '全部项目' },
  ...availableProjects.value.map((project) => ({
    id: project.project_id,
    label: `${project.project_id} · ${project.project_name}`,
  })),
])

const filtered = computed(() => {
  if (!severityFilter.value) return triggers.value
  return triggers.value.filter((item) => item.severity === severityFilter.value)
})

const severityOptions = computed(() => {
  const set = new Set(triggers.value.map((item) => item.severity))
  return Array.from(set).sort()
})

function syncProjectFilter() {
  projectIdFilter.value = projectFilter.value ?? ''
}

onMounted(() => {
  syncProjectFilter()
  loadTriggers()
})

watch(selectedProjectId, () => {
  if (selectedProjectId.value === ALL_PROJECTS_VALUE) {
    projectIdFilter.value = ''
  } else {
    syncProjectFilter()
  }
  loadTriggers()
})

watch([projectIdFilter, ruleIdFilter], loadTriggers)

async function loadTriggers() {
  loading.value = true
  errorMessage.value = ''
  try {
    triggers.value = await api.ruleTriggers({
      project_id: projectIdFilter.value || undefined,
      rule_id: ruleIdFilter.value || undefined,
    })
    selected.value = triggers.value[0] ?? null
  } catch {
    errorMessage.value = '规则触发日志加载失败，请确认后端已连接。'
    triggers.value = []
    selected.value = null
  } finally {
    loading.value = false
  }
}

function clearFilters() {
  severityFilter.value = ''
  ruleIdFilter.value = ''
  projectIdFilter.value = projectFilter.value ?? ''
}

function selectTrigger(item: RuleTriggerLog) {
  selected.value = item
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

function objectLabel(item: RuleTriggerLog): string {
  return `${item.object_type} · ${item.object_id}`
}

function formatEvidence(value: unknown): string {
  if (value == null) return '无证据摘要'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function formatTime(iso: string): string {
  return iso.replace('T', ' ').slice(0, 19)
}
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Rules / Strong Rules First</p>
        <h2>强规则触发日志</h2>
      </div>
      <div class="work-order-summary rules-filters">
        <span class="status-pill">
          <Zap :size="14" />
          {{ filtered.length }} 条记录
        </span>
        <label class="filter-chip">
          <Filter :size="14" />
          <select v-model="projectIdFilter">
            <option v-for="option in projectOptions" :key="option.id || 'all'" :value="option.id">
              {{ option.label }}
            </option>
          </select>
        </label>
        <label class="filter-chip">
          <Filter :size="14" />
          <select v-model="ruleIdFilter">
            <option value="">全部规则</option>
            <option v-for="rule in STRONG_RULE_OPTIONS" :key="rule.id" :value="rule.id">
              {{ rule.id }} · {{ rule.name }}
            </option>
          </select>
        </label>
        <label class="filter-chip">
          <Filter :size="14" />
          <select v-model="severityFilter">
            <option value="">全部严重度</option>
            <option v-for="level in severityOptions" :key="level" :value="level">{{ level }}</option>
          </select>
        </label>
        <button type="button" class="action-button" :disabled="loading" @click="clearFilters">重置</button>
      </div>
    </div>

    <div v-if="errorMessage" class="notice notice-error panel-wide">{{ errorMessage }}</div>

    <section class="panel panel-wide rules-board">
      <div v-if="loading" class="loading-panel">加载规则触发记录…</div>
      <template v-else-if="filtered.length">
        <div class="rules-list">
          <div
            v-for="item in filtered"
            :key="item.trigger_id"
            class="rule-card"
            :class="{ 'is-selected': selected?.trigger_id === item.trigger_id }"
            @click="selectTrigger(item)"
          >
            <div class="rule-card-head">
              <code class="metric-code">{{ item.rule_id }}</code>
              <span class="status-chip" :class="severityClass(item.severity)">{{ item.severity }}</span>
            </div>
            <strong>{{ item.rule_name }}</strong>
            <small>{{ objectLabel(item) }} · {{ item.project_id || '—' }}</small>
            <span class="rule-time">{{ formatTime(item.created_at) }}</span>
          </div>
        </div>

        <aside class="rules-detail" v-if="selected">
          <div class="detail-head">
            <div>
              <p class="eyebrow">{{ selected.trigger_id }}</p>
              <h3>{{ selected.rule_name }}</h3>
            </div>
            <span class="status-chip" :class="severityClass(selected.severity)">{{ selected.severity }}</span>
          </div>

          <div class="detail-grid">
            <span>规则 ID</span><strong><code class="metric-code">{{ selected.rule_id }}</code></strong>
            <span>对象</span><strong>{{ objectLabel(selected) }}</strong>
            <span>项目</span><strong>{{ selected.project_id || '—' }}</strong>
            <span>触发时间</span><strong>{{ formatTime(selected.created_at) }}</strong>
          </div>

          <div class="detail-section governance-card">
            <h3>
              <AlertOctagon :size="16" style="vertical-align: -2px; margin-right: 6px" />
              证据摘要
            </h3>
            <pre class="evidence-block">{{ formatEvidence(selected.evidence) }}</pre>
          </div>

          <p class="form-help">强规则结论优先于 LLM 判断；触发记录用于画像解释、工单联动与审计追溯。</p>
        </aside>
      </template>
      <p v-else class="empty-state">
        {{ loading ? '加载中…' : '暂无匹配的规则触发记录，可调整筛选或先执行画像重算。' }}
      </p>
    </section>
  </section>
</template>

<style scoped>
.rules-filters {
  flex-wrap: wrap;
  justify-content: flex-end;
}
</style>
