<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import type { ProfileData } from '../types/api'

const subOptions = [
  { id: 'S001', label: 'S001 · 华东建设劳务' },
  { id: 'S002', label: 'S002 · 中建安装劳务' },
  { id: 'S003', label: 'S003 · 广东宏大建设' },
]

const profile = ref<ProfileData>({
  subcontractor_id: 'S001',
  subcontractor_name: '加载中…',
  calc_date: '',
  calculated_at: '',
  total_risk_score: 0,
  risk_level: 'low',
  risk_tags: null,
  data_completeness: 0,
  explanation: null,
  suggestion: null,
})

const subId = ref('S001')
const loading = ref(true)
const loadError = ref('')

async function loadProfile() {
  loading.value = true
  loadError.value = ''
  try {
    profile.value = await api.subcontractorProfile(subId.value)
  } catch {
    loadError.value = '分包商画像加载失败，请检查后端连接。'
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)
watch(subId, loadProfile)

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
        <p class="eyebrow">Profile / Subcontractor</p>
        <h2>{{ profile.subcontractor_name || profile.subcontractor_id || '分包商安全履约画像' }}</h2>
      </div>
      <div class="entity-switcher">
        <label>
          <span>切换分包商</span>
          <select v-model="subId">
            <option v-for="item in subOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>
        <RiskBadge v-if="!loading" :level="profile.risk_level" />
      </div>
    </div>

    <div v-if="loadError" class="notice notice-error panel-wide">{{ loadError }}</div>

    <section class="panel panel-wide">
      <div v-if="loading" class="loading-panel">加载分包商画像…</div>
      <template v-else>
        <div class="profile-score compact">
          <strong>{{ profile.total_risk_score }}</strong>
          <div class="profile-meta">
            <span>{{ profile.subcontractor_id }} · 跨项目履约摘要</span>
            <span v-if="profile.overdue_rectification_ratio != null">
              超期整改率 {{ Math.round(profile.overdue_rectification_ratio * 100) }}%
            </span>
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
    <section class="panel">
      <h3>管理建议</h3>
      <p>{{ loading ? '…' : profile.suggestion || '对超期整改和高风险班组开展专项约谈，跟踪复查完成率。' }}</p>
    </section>
  </section>
</template>
