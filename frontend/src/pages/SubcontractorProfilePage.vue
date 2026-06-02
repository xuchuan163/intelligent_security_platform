<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import type { ProfileData } from '../types/api'

const profile = ref<ProfileData>({
  subcontractor_id: 'S001',
  subcontractor_name: '加载中...',
  calc_date: '',
  total_risk_score: 0,
  risk_level: 'low',
  risk_tags: null,
  data_completeness: 0,
  explanation: null,
  suggestion: null,
})

const subId = ref('S001')

onMounted(async () => {
  try {
    profile.value = await api.subcontractorProfile(subId.value)
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
        <p class="eyebrow">Profile / Subcontractor</p>
        <h2>{{ profile.subcontractor_name || profile.subcontractor_id || '分包商安全履约画像' }}</h2>
      </div>
      <RiskBadge :level="profile.risk_level" />
    </div>
    <section class="panel panel-wide">
      <div class="profile-score compact">
        <strong>{{ profile.total_risk_score }}</strong>
        <span>{{ profile.subcontractor_id }} 跨项目履约风险摘要</span>
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
      <h3>管理建议</h3>
      <p>对超期整改和高风险班组开展专项约谈，跟踪复查完成率。</p>
    </section>
  </section>
</template>
