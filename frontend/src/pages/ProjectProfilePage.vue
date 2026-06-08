<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import RiskBadge from '../components/RiskBadge.vue'
import { useScopeContext } from '../composables/useScopeContext'
import { ALL_PROJECTS_VALUE } from '../scopeView'
import type { ProfileData } from '../types/api'

const { availableProjects, projectFilter, selectedProjectId } = useScopeContext()

const profile = ref<ProfileData>({
  project_id: 'P001',
  project_name: '加载中…',
  calc_date: '',
  calculated_at: '',
  total_risk_score: 0,
  risk_level: 'low',
  risk_tags: null,
  data_completeness: 0,
  explanation: null,
  suggestion: null,
})

const projectId = ref('P001')
const loading = ref(true)
const loadError = ref('')

const projectOptions = computed(() =>
  availableProjects.value.map((project) => ({
    id: project.project_id,
    label: `${project.project_id} · ${project.project_name}`,
  })),
)

function syncProjectSelection() {
  if (projectFilter.value) {
    projectId.value = projectFilter.value
    return
  }
  if (projectOptions.value.length > 0) {
    projectId.value = projectOptions.value[0].id
  }
}

async function loadProfile() {
  loading.value = true
  loadError.value = ''
  try {
    profile.value = await api.projectProfile(projectId.value)
  } catch {
    loadError.value = '画像加载失败，请确认后端已启动且项目 ID 有效。'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  syncProjectSelection()
  loadProfile()
})

watch(selectedProjectId, () => {
  if (selectedProjectId.value === ALL_PROJECTS_VALUE) {
    return
  }
  syncProjectSelection()
  loadProfile()
})

watch(projectId, loadProfile)

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
        <p class="eyebrow">Profiles / Project</p>
        <h2>项目安全风险画像</h2>
      </div>
      <label class="entity-switcher">
        <span>切换项目</span>
        <select v-model="projectId" :disabled="projectOptions.length <= 1">
          <option v-for="option in projectOptions" :key="option.id" :value="option.id">
            {{ option.label }}
          </option>
        </select>
      </label>
    </div>

    <div v-if="loading" class="loading-panel">加载项目画像…</div>
    <p v-else-if="loadError" class="empty-state">{{ loadError }}</p>

    <template v-else>
      <section class="panel panel-wide profile-hero">
        <div>
          <p class="eyebrow">{{ profile.project_id }}</p>
          <h3>{{ profile.project_name }}</h3>
          <p class="profile-meta">计算日期 {{ profile.calc_date }} · 完整度 {{ profile.data_completeness ?? 0 }}%</p>
        </div>
        <div class="profile-score">
          <span class="profile-score-value">{{ profile.total_risk_score }}</span>
          <RiskBadge :level="profile.risk_level" />
        </div>
      </section>

      <section class="panel">
        <div class="panel-head">
          <h3>风险标签</h3>
        </div>
        <div class="tag-list">
          <span v-for="tag in tags()" :key="tag" class="tag-chip">{{ tag }}</span>
          <p v-if="!tags().length" class="empty-state">暂无风险标签</p>
        </div>
      </section>

      <section class="panel panel-wide">
        <div class="panel-head">
          <h3>画像解释</h3>
        </div>
        <p class="profile-copy">{{ profile.explanation || '暂无解释文案' }}</p>
      </section>

      <section class="panel panel-wide">
        <div class="panel-head">
          <h3>处置建议</h3>
        </div>
        <p class="profile-copy">{{ profile.suggestion || '暂无建议' }}</p>
      </section>
    </template>
  </section>
</template>
