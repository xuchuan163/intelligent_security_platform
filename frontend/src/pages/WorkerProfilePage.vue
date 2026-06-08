<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import type { ProfileData } from '../types/api'

const workerOptions = [
  { id: 'W001', label: 'W001 · 电工' },
  { id: 'W002', label: 'W002 · 架子工' },
  { id: 'W003', label: 'W003 · 塔吊司机（证过期）' },
  { id: 'W005', label: 'W005 · 普工（高风险）' },
]

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

const workerId = ref('W002')
const loading = ref(true)
const loadError = ref('')

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

onMounted(loadProfile)
watch(workerId, loadProfile)

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
          <select v-model="workerId">
            <option v-for="item in workerOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <RiskBadge v-if="!loading" :level="profile.risk_level" />
      </div>
    </div>

    <div v-if="loadError" class="notice notice-error panel-wide">{{ loadError }}</div>

    <section class="panel panel-wide">
      <div v-if="loading" class="loading-panel">加载工人画像…</div>
      <template v-else>
        <div class="profile-score compact">
          <strong>{{ profile.total_risk_score }}</strong>
          <div class="profile-meta">
            <span>{{ profile.worker_id }} · 脱敏展示</span>
            <span v-if="profile.confidence_level">置信度 {{ profile.confidence_level }}</span>
          </div>
        </div>
        <div class="tag-row" v-if="tags().length > 0">
          <span v-for="tag in tags()" :key="tag" class="risk-tag">{{ tag }}</span>
        </div>
      </template>
    </section>
    <section class="panel">
      <h3>风险解释</h3>
      <p>{{ loading ? '…' : profile.explanation || '暂无解释' }}</p>
    </section>
    <section class="panel governance-card">
      <h3>适用边界</h3>
      <p>画像用于培训、提醒和作业适配，不作为处罚、清退或岗位调整的唯一依据。</p>
    </section>
  </section>
</template>
