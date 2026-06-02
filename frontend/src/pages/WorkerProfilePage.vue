<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import type { ProfileData } from '../types/api'

const profile = ref<ProfileData>({
  worker_id: 'W002',
  worker_name_masked: '加载中...',
  calc_date: '',
  total_risk_score: 0,
  risk_level: 'low',
  risk_tags: null,
  data_completeness: 0,
  explanation: null,
  suggestion: null,
})

const workerId = ref('W002')

onMounted(async () => {
  try {
    profile.value = await api.workerProfile(workerId.value)
  } catch {}
})

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
      <RiskBadge :level="profile.risk_level" />
    </div>
    <section class="panel panel-wide">
      <div class="profile-score compact">
        <strong>{{ profile.total_risk_score }}</strong>
        <span>{{ profile.worker_id }} 仅展示脱敏画像摘要</span>
      </div>
      <div class="tag-row" v-if="tags().length > 0">
        <span v-for="tag in tags()" :key="tag" class="risk-tag">{{ tag }}</span>
      </div>
    </section>
    <section class="panel">
      <h3>风险解释</h3>
      <p>{{ profile.explanation || '暂无解释' }}</p>
    </section>
    <section class="panel">
      <h3>适用边界</h3>
      <p>画像用于培训、提醒和作业适配，不作为处罚、清退或岗位调整的唯一依据。</p>
    </section>
  </section>
</template>
