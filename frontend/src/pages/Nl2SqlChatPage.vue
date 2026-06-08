<script setup lang="ts">
import { MessageCircleQuestion, Send, Sparkles } from 'lucide-vue-next'
import { computed, ref } from 'vue'

import { api } from '../api/client'
import AgentFeedbackBar from '../components/AgentFeedbackBar.vue'
import type { Nl2SqlQueryResult } from '../types/api'

interface ChatTurn {
  role: 'user' | 'assistant'
  text: string
}

const sessionId = ref(`NL2SQL-${crypto.randomUUID()}`)
const question = ref('查询最近风险较高的项目')
const clarificationReply = ref('')
const useMockProvider = ref(true)
const mockOutput = ref('CLARIFICATION_REQUIRED: please provide a time range and risk definition')
const mockFollowUpOutput = ref(
  "SELECT project_id, risk_level FROM project_risk_profile WHERE risk_level = 'high'",
)
const executeQuery = ref(false)
const loading = ref(false)
const errorMessage = ref('')
const turns = ref<ChatTurn[]>([])
const lastResult = ref<Nl2SqlQueryResult | null>(null)
const clarificationId = ref<string | null>(null)
const feedbackTaskId = computed(() => lastResult.value?.audit_id ?? clarificationId.value ?? '')

const awaitingClarification = computed(() => Boolean(lastResult.value?.awaiting_clarification))

async function askInitial() {
  if (!question.value.trim()) return
  loading.value = true
  errorMessage.value = ''
  turns.value.push({ role: 'user', text: question.value })
  try {
    const result = await api.nl2sqlQuery({
      question: question.value,
      execute: executeQuery.value,
      provider: useMockProvider.value ? 'mock' : undefined,
      mock_llm_output: useMockProvider.value ? mockOutput.value : undefined,
      session_id: sessionId.value,
    })
    lastResult.value = result
    clarificationId.value = result.clarification_id ?? null
    if (result.awaiting_clarification) {
      turns.value.push({
        role: 'assistant',
        text: `需要澄清：${result.clarification_prompt ?? result.rejection_reason ?? '请补充业务条件'}`,
      })
    } else if (result.status === 'audit_passed' || result.status === 'executed') {
      turns.value.push({
        role: 'assistant',
        text: `SQL 已生成：${result.sanitized_sql ?? ''}`,
      })
    } else {
      turns.value.push({
        role: 'assistant',
        text: `未生成 SQL（${result.status}）：${result.rejection_reason ?? '请调整问题'}`,
      })
    }
  } catch {
    errorMessage.value = '问数请求失败，请确认后端已连接且本地 mock provider 可用。'
  } finally {
    loading.value = false
  }
}

async function submitClarification() {
  if (!clarificationId.value || !clarificationReply.value.trim()) return
  loading.value = true
  errorMessage.value = ''
  turns.value.push({ role: 'user', text: clarificationReply.value })
  try {
    const result = await api.nl2sqlQuery({
      clarification_id: clarificationId.value,
      clarification_reply: clarificationReply.value,
      execute: executeQuery.value,
      provider: useMockProvider.value ? 'mock' : undefined,
      mock_llm_output: useMockProvider.value ? mockFollowUpOutput.value : undefined,
      session_id: sessionId.value,
    })
    lastResult.value = result
    if (result.status === 'audit_passed' || result.status === 'executed') {
      turns.value.push({
        role: 'assistant',
        text: `澄清后 SQL：${result.sanitized_sql ?? ''}`,
      })
      clarificationId.value = null
      clarificationReply.value = ''
    } else if (result.awaiting_clarification) {
      turns.value.push({
        role: 'assistant',
        text: `仍需澄清：${result.clarification_prompt ?? result.rejection_reason ?? ''}`,
      })
    } else {
      turns.value.push({
        role: 'assistant',
        text: `澄清后仍未通过（${result.status}）：${result.rejection_reason ?? ''}`,
      })
    }
  } catch {
    errorMessage.value = '澄清续问失败，请检查 clarification_id 是否仍有效。'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">NL2SQL / Clarification</p>
        <h2>智能问数 · 多轮澄清</h2>
      </div>
    </div>

    <section class="panel panel-wide">
      <div class="panel-head">
        <h3>对话</h3>
        <span v-if="awaitingClarification" class="status-chip status-waiting_review">等待澄清</span>
      </div>
      <div class="list">
        <div v-for="(turn, index) in turns" :key="index" class="list-row">
          <strong>{{ turn.role === 'user' ? '用户' : '系统' }}</strong>
          <span>{{ turn.text }}</span>
        </div>
        <p v-if="!turns.length" class="empty-state">输入业务问题开始问数。歧义问题会进入澄清流程。</p>
      </div>
    </section>

    <section v-if="!awaitingClarification" class="panel panel-wide">
      <div class="panel-head">
        <h3>首轮提问</h3>
      </div>
      <label class="form-span">
        <span>问题</span>
        <textarea v-model="question" rows="2" />
      </label>
      <label class="checkbox-row">
        <input v-model="useMockProvider" type="checkbox" />
        <span>使用本地 mock provider（演示）</span>
      </label>
      <label v-if="useMockProvider" class="form-span">
        <span>Mock 输出</span>
        <textarea v-model="mockOutput" rows="2" />
      </label>
      <label class="checkbox-row">
        <input v-model="executeQuery" type="checkbox" />
        <span>审计通过后执行只读 SQL</span>
      </label>
      <button type="button" class="action-button action-primary" :disabled="loading" @click="askInitial">
        <Sparkles :size="16" />
        {{ loading ? '处理中…' : '发起问数' }}
      </button>
    </section>

    <section v-else class="panel panel-wide">
      <div class="panel-head">
        <h3>澄清回复</h3>
        <span>{{ lastResult?.clarification_prompt }}</span>
      </div>
      <label class="form-span">
        <span>补充条件</span>
        <textarea v-model="clarificationReply" rows="2" placeholder="例如：最近30天，高风险指 risk_level=high" />
      </label>
      <label v-if="useMockProvider" class="form-span">
        <span>澄清后 Mock 输出</span>
        <textarea v-model="mockFollowUpOutput" rows="2" />
      </label>
      <button type="button" class="action-button action-primary" :disabled="loading" @click="submitClarification">
        <Send :size="16" />
        {{ loading ? '处理中…' : '提交澄清并续问' }}
      </button>
    </section>

    <AgentFeedbackBar
      v-if="feedbackTaskId && lastResult"
      :task-id="feedbackTaskId"
      agent-name="nl2sql_analyst"
      :original-output="lastResult as unknown as Record<string, unknown>"
    />

    <section v-if="lastResult?.rows?.length" class="panel panel-wide">
      <div class="panel-head">
        <h3>查询结果</h3>
        <span>{{ lastResult.row_count }} 行</span>
      </div>
      <pre class="profile-copy">{{ JSON.stringify(lastResult.rows, null, 2) }}</pre>
    </section>

    <p v-if="errorMessage" class="empty-state">{{ errorMessage }}</p>
    <p v-if="lastResult?.need_human_review" class="status-chip status-waiting_review">
      <MessageCircleQuestion :size="14" />
      问数结果仅供参考，需人工复核
    </p>
  </section>
</template>
