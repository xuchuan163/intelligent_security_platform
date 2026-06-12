<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import { useScopeContext } from '../composables/useScopeContext'
import type { ProfileData, WorkerListItem } from '../types/api'

const { projectFilter } = useScopeContext()

const profile = ref<ProfileData>({
  worker_id: 'W002',
  worker_name_masked: '加载中…',
  calc_date: '',
  calculated_at: '',
  total_risk_score: 0,
  risk_level: 'low',
  risk_tags: null,
  data_completeness: 0,
  explanation: null,
  suggestion: null,
})

const workers = ref<WorkerListItem[]>([])
const workerId = ref('W002')
const loading = ref(true)
const listLoading = ref(true)
const loadError = ref('')

const workerOptions = computed(() =>
  workers.value.map((worker) => {
    const riskHint =
      worker.risk_level && ['high', 'critical'].includes(worker.risk_level) ? ` · ${worker.risk_level}` : ''
    const certHint =
      worker.special_cert_status === 'expired'
        ? '（证过期）'
        : worker.special_cert_status === 'missing'
          ? '（无证）'
          : ''
    return {
      id: worker.worker_id,
      label: `${worker.worker_id} · ${worker.work_type || '工人'}${certHint}${riskHint}`,
    }
  }),
)

async function loadWorkers() {
  listLoading.value = true
  try {
    const response = await api.workers({
      project_id: projectFilter.value || undefined,
      limit: 200,
    })
    workers.value = response.items
    if (workers.value.length > 0 && !workers.value.some((item) => item.worker_id === workerId.value)) {
      workerId.value = workers.value[0].worker_id
    }
  } catch {
    workers.value = []
  } finally {
    listLoading.value = false
  }
}

async function loadProfile() {
  loading.value = true
  loadError.value = ''
  try {
    profile.value = await api.workerProfile(workerId.value)
  } catch {
    loadError.value = '工人画像加载失败，请检查后端连接。'
  } finally {
    loading.value = false
  }
}

async function refreshPage() {
  await loadWorkers()
  await loadProfile()
}

onMounted(refreshPage)
watch(workerId, loadProfile)
watch(projectFilter, refreshPage)

function tags(): string[] {
  if (!profile.value.risk_tags) return []
  if (Array.isArray(profile.value.risk_tags)) return profile.value.risk_tags
  if (typeof profile.value.risk_tags === 'object' && 'tags' in profile.value.risk_tags) {
    return (profile.value.risk_tags as { tags: string[] }).tags
  }
  return []
}
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Profile / Worker</p>
        <h2>{{ profile.worker_name_masked || profile.worker_id || '工人安全风险画像' }}</h2>
      </div>
      <div class="entity-switcher">
        <label>
          <span>切换工人</span>
          <select v-model="workerId" :disabled="listLoading || workerOptions.length === 0">
            <option v-if="listLoading" value="">加载工人列表…</option>
            <option v-else-if="workerOptions.length === 0" value="">暂无工人数据</option>
            <option v-for="item in workerOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <RiskBadge v-if="!loading" :level="profile.risk_level" />
      </div>
    </div>

    <p v-if="!listLoading && workers.length > 0" class="eyebrow panel-wide">
      当前共 {{ workers.length }} 名工人{{ projectFilter ? `（项目 ${projectFilter}）` : '' }}
    </p>

    <div v-if="loadError" class="notice notice-error panel-wide">{{ loadError }}</div>

    <section class="panel panel-wide">
      <div v-if="loading" class="loading-panel">加载工人画像…</div>
      <template v-else>
        <div class="profile-score compact">
          <div>
            <span class="score-label">综合风险分</span>
            <strong class="score-value">{{ profile.total_risk_score }}</strong>
          </div>
          <div>
            <span class="score-label">数据完整度</span>
            <strong>{{ profile.data_completeness ?? 0 }}%</strong>
          </div>
          <div>
            <span class="score-label">计算日期</span>
            <strong>{{ profile.calc_date || profile.calculated_at }}</strong>
          </div>
        </div>

        <p class="profile-explanation">{{ profile.explanation }}</p>
        <p v-if="profile.suggestion" class="profile-suggestion">{{ profile.suggestion }}</p>

        <div v-if="tags().length" class="tag-row">
          <span v-for="tag in tags()" :key="tag" class="tag-chip">{{ tag }}</span>
        </div>
      </template>
    </section>
  </section>
</template>
