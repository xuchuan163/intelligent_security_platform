<script setup lang="ts">
import { AlertTriangle, ClipboardCheck, Sparkles } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import { api } from '../api/client'
import AgentFeedbackBar from '../components/AgentFeedbackBar.vue'
import { useScopeContext } from '../composables/useScopeContext'
import { projectFilterParam } from '../scopeView'
import type { AgentAskResult } from '../types/api'

const router = useRouter()
const { selectedProjectId } = useScopeContext()

const sessionId = ref(`HAZARD-${crypto.randomUUID()}`)
const hazardId = ref('H002')
const message = ref('这个脚手架隐患应该怎么整改')
const proposeWorkOrder = ref(false)
const demoMode = ref(true)
const llmEnhance = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const result = ref<AgentAskResult | null>(null)

const projectId = computed(() => projectFilterParam(selectedProjectId.value) ?? 'P001')
const suggestion = computed(() => {
  const draftStep = result.value?.step_results?.find((step) => step.action === 'draft_rectification_suggestion')
  return (draftStep?.output_summary ?? null) as Record<string, unknown> | null
})
const approvalId = computed(() => {
  const createStep = result.value?.step_results?.find((step) => step.tool_name === 'work_orders.create')
  return createStep?.approval_id ?? null
})
const feedbackTaskId = computed(() => result.value?.run_id ?? approvalId.value ?? '')
const draftStatus = computed(() => {
  const status = suggestion.value?.status
  return typeof status === 'string' ? status : null
})
const executionSummary = computed(() => {
  if (!result.value) return ''
  const parts = [
    result.value.target_agent,
    result.value.dag_status,
    result.value.memory_source ? `memory=${result.value.memory_source}` : null,
  ].filter(Boolean)
  return parts.join(' · ')
})

async function runAdvisor() {
  loading.value = true
  errorMessage.value = ''
  result.value = null
  try {
    result.value = await api.agentAsk(message.value, {
      context: {
        project_id: projectId.value,
        hazard_id: hazardId.value,
        propose_work_order: proposeWorkOrder.value,
        demo_mode: demoMode.value && !llmEnhance.value,
        llm_enhance: llmEnhance.value,
      },
      execution_mode: 'controlled_execute',
      session_id: sessionId.value,
      timeoutMs: llmEnhance.value ? 60000 : 20000,
    })
    if (draftStatus.value === 'hazard_not_found') {
      errorMessage.value =
        (suggestion.value?.message as string | undefined) ??
        '未找到隐患证据，请确认 hazard_id 与项目范围正确（演示数据推荐 H002 / P001）。'
    } else if (!suggestion.value && result.value.dag_status === 'blocked') {
      errorMessage.value = result.value.blocked_reason ?? 'DAG 执行被阻断，请检查项目权限或上下文参数。'
    } else if (!suggestion.value) {
      errorMessage.value = '未生成整改建议，请确认问题描述包含「隐患/整改」且 hazard_id 有效。'
    }
  } catch (error: unknown) {
    const axiosMessage =
      typeof error === 'object' &&
      error !== null &&
      'response' in error &&
      typeof (error as { response?: { data?: { message?: string } } }).response?.data?.message === 'string'
        ? (error as { response: { data: { message: string } } }).response.data.message
        : null
    errorMessage.value =
      axiosMessage ??
      '隐患整改 Agent 调用失败，请确认后端已连接、Redis 可用，且 hazard_id 属于当前项目。'
  } finally {
    loading.value = false
  }
}

function openApprovals() {
  router.push('/agent/approvals')
}
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Agent / Hazard Rectification</p>
        <h2>隐患整改顾问</h2>
      </div>
    </div>

    <section class="panel panel-wide">
      <div class="panel-head">
        <h3>分析参数</h3>
        <span>证据引用 + 人工确认开单</span>
      </div>
      <div class="form-grid">
        <label>
          <span>项目</span>
          <input :value="projectId" readonly />
        </label>
        <label>
          <span>隐患 ID</span>
          <input v-model="hazardId" placeholder="H002" />
        </label>
        <label class="form-span">
          <span>问题描述</span>
          <textarea v-model="message" rows="3" />
        </label>
        <label class="checkbox-row">
          <input v-model="proposeWorkOrder" type="checkbox" />
          <span>同时申请创建整改工单（需审批）</span>
        </label>
        <label class="checkbox-row">
          <input v-model="demoMode" type="checkbox" />
          <span>演示模式（跳过 LLM 增强，秒级返回证据化建议）</span>
        </label>
        <label class="checkbox-row">
          <input v-model="llmEnhance" type="checkbox" :disabled="demoMode" />
          <span>启用 LLM 增强（需 DASHSCOPE_API_KEY，响应较慢）</span>
        </label>
      </div>
      <div class="action-row">
        <button type="button" class="action-button action-primary" :disabled="loading" @click="runAdvisor">
          <Sparkles :size="16" />
          {{ loading ? '分析中…' : '生成整改建议' }}
        </button>
        <button v-if="approvalId" type="button" class="action-button" @click="openApprovals">
          <ClipboardCheck :size="16" />
          前往审批 {{ approvalId }}
        </button>
      </div>
      <p v-if="executionSummary" class="muted-text">执行摘要：{{ executionSummary }}</p>
      <p v-if="errorMessage" class="empty-state">{{ errorMessage }}</p>
    </section>

    <AgentFeedbackBar
      v-if="feedbackTaskId && suggestion"
      :task-id="feedbackTaskId"
      agent-name="hazard_rectification_advisor"
      :project-id="projectId"
      :original-output="suggestion"
    />

    <section v-if="suggestion" class="panel panel-wide">
      <div class="panel-head">
        <h3>整改建议</h3>
        <span class="status-chip status-waiting_review">需人工复核</span>
      </div>
      <div class="list">
        <div
          v-for="(item, index) in (suggestion.rectification_suggestions as string[] | undefined) ?? []"
          :key="`${index}-${item}`"
          class="list-row"
        >
          <AlertTriangle :size="16" />
          <strong>{{ item }}</strong>
        </div>
      </div>
      <div class="panel-head" style="margin-top: 16px">
        <h3>证据引用</h3>
      </div>
      <div class="tag-list">
        <span
          v-for="ref in (suggestion.evidence as Array<{ label?: string; ref_id?: string }> | undefined) ?? []"
          :key="ref.ref_id"
          class="tag-chip"
        >
          {{ ref.label ?? ref.ref_id }}
        </span>
      </div>
    </section>
  </section>
</template>
