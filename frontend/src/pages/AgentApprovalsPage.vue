<script setup lang="ts">
import {
  AlertCircle,
  CheckCircle2,
  ClipboardCheck,
  Play,
  RefreshCw,
  ShieldCheck,
  XCircle,
  Zap,
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { api } from '../api/client'
import AgentFeedbackBar from '../components/AgentFeedbackBar.vue'
import {
  approvalStatusClass,
  approvalStatusLabel,
  canApprove,
  canExecute,
} from '../agentApprovalFlow'
import type { AgentApprovalRequest, CurrentUser } from '../types/api'

const props = defineProps<{
  currentUser?: CurrentUser | null
  backendOnline?: boolean
}>()

const items = ref<AgentApprovalRequest[]>([])
const selected = ref<AgentApprovalRequest | null>(null)
const loading = ref(true)
const acting = ref(false)
const generating = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const statusFilter = ref('pending')
const demoActorId = ref('director')
const demoSessionId = ref(`AGENT-${crypto.randomUUID()}`)

const demoActors = [
  {
    id: 'director',
    label: '安全总监（审批/执行）',
    userId: 'U-DIR-01',
    userName: '王总监',
    role: 'safety_director',
    subcontractorId: null,
  },
  {
    id: 'agent',
    label: 'Agent 请求方',
    userId: 'U-AGENT-01',
    userName: '智能体',
    role: 'platform_admin',
    subcontractorId: null,
  },
]

const demoForm = reactive({
  work_order_id: 'WO-DEMO-P002-001',
  project_id: 'P002',
  action: 'confirm',
  message: '请审批派发工单 WO-DEMO-P002-001',
})

const decisionComment = ref('人工复核通过，符合安全管控要求。')

const selectedDemoActor = computed(() => demoActors.find((actor) => actor.id === demoActorId.value) ?? demoActors[0])
const pendingCount = computed(() => items.value.filter((item) => item.status === 'pending').length)

onMounted(async () => {
  applyDemoActor()
  await loadApprovals()
})

watch(statusFilter, loadApprovals)

function applyDemoActor() {
  const actor = selectedDemoActor.value
  api.setMockAuthContext({
    userId: actor.userId,
    userName: actor.userName,
    role: actor.role,
    tenantId: 'CSCEC',
    companyId: 'CSCEC',
    orgPath: 'CSCEC/P002',
    scopeType: 'project',
    dataScope: 'org',
    authorizedProjectIds: ['P002'],
    subcontractorId: actor.subcontractorId,
  })
}

async function changeDemoActor() {
  applyDemoActor()
  await loadApprovals()
  if (selected.value) {
    await openDetail(selected.value.approval_id)
  }
}

async function loadApprovals() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await api.agentApprovals(statusFilter.value)
    items.value = result.items
    if (!selected.value && result.items.length > 0) {
      await openDetail(result.items[0].approval_id)
    } else if (selected.value) {
      const refreshed = result.items.find((item) => item.approval_id === selected.value?.approval_id)
      selected.value = refreshed ?? null
    }
  } catch {
    errorMessage.value = '审批队列加载失败，请确认后端已连接且当前岗位有项目权限。'
    items.value = []
    selected.value = null
  } finally {
    loading.value = false
  }
}

async function openDetail(approvalId: string) {
  errorMessage.value = ''
  try {
    selected.value = await api.agentApprovalDetail(approvalId)
  } catch {
    errorMessage.value = `${approvalId} 详情加载失败。`
  }
}

async function generateApprovalRequest() {
  generating.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const agentActor = demoActors.find((actor) => actor.id === 'agent') ?? demoActors[1]
    api.setMockAuthContext({
      userId: agentActor.userId,
      userName: agentActor.userName,
      role: agentActor.role,
      tenantId: 'CSCEC',
      companyId: 'CSCEC',
      orgPath: 'CSCEC/P002',
      scopeType: 'project',
      dataScope: 'org',
      authorizedProjectIds: ['P002'],
    })

    const result = await api.agentAsk(demoForm.message, {
      execution_mode: 'controlled_execute',
      context: {
        project_id: demoForm.project_id,
        work_order_id: demoForm.work_order_id,
        action: demoForm.action,
      },
      session_id: demoSessionId.value,
    })

    const writeStep = result.step_results?.find((step) => step.status === 'approval_required')
    if (writeStep?.approval_id) {
      successMessage.value = `已生成审批单 ${writeStep.approval_id}，请切换为安全总监处理。`
      statusFilter.value = 'pending'
      applyDemoActor()
      await loadApprovals()
      await openDetail(writeStep.approval_id)
    } else {
      successMessage.value = `DAG 状态：${result.dag_status ?? 'unknown'}，未产生写操作审批单。`
    }
  } catch {
    errorMessage.value = '生成审批请求失败，请确认工单 ID 存在且处于可流转状态。'
  } finally {
    generating.value = false
    applyDemoActor()
  }
}

async function approveSelected() {
  if (!selected.value) return
  await runDecision('approve')
}

async function rejectSelected() {
  if (!selected.value) return
  await runDecision('reject')
}

async function executeSelected() {
  if (!selected.value) return
  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const result = await api.executeAgentApproval(selected.value.approval_id)
    selected.value = result
    successMessage.value = `已执行 ${result.approval_id}，工单新状态：${String(result.execution_result?.new_status ?? '—')}`
    await loadApprovals()
  } catch {
    errorMessage.value = '执行失败，请确认已批准、岗位为安全总监且工单状态允许该动作。'
    if (selected.value) {
      await openDetail(selected.value.approval_id)
    }
  } finally {
    acting.value = false
  }
}

async function runDecision(kind: 'approve' | 'reject') {
  if (!selected.value) return
  acting.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const result =
      kind === 'approve'
        ? await api.approveAgentRequest(selected.value.approval_id, decisionComment.value)
        : await api.rejectAgentRequest(selected.value.approval_id, decisionComment.value)
    selected.value = result
    successMessage.value = `${result.approval_id} 已${kind === 'approve' ? '批准' : '驳回'}`
    await loadApprovals()
  } catch {
    errorMessage.value = `${kind === 'approve' ? '批准' : '驳回'}失败，请确认单据仍为 pending 且当前账号有权限。`
  } finally {
    acting.value = false
  }
}

function formatTime(value: string | null | undefined): string {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 19)
}

function formatJson(value: unknown): string {
  if (value == null) return '—'
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
</script>

<template>
  <section class="page-grid approval-page">
    <div class="page-title">
      <div>
        <p class="eyebrow">Agent / Human Approval</p>
        <h2>Agent 审批执行台</h2>
      </div>
      <div class="work-order-summary">
        <label class="role-switcher">
          <span>演示岗位</span>
          <select v-model="demoActorId" @change="changeDemoActor">
            <option v-for="actor in demoActors" :key="actor.id" :value="actor.id">
              {{ actor.label }}
            </option>
          </select>
        </label>
        <span>待审批 {{ pendingCount }}</span>
        <button type="button" class="icon-button" title="刷新列表" @click="loadApprovals">
          <RefreshCw :size="16" />
        </button>
      </div>
    </div>

    <section class="panel panel-wide approval-demo-panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Demo Generator</p>
          <h3>生成 Agent 写操作审批单</h3>
          <span>通过 `controlled_execute` 触发 `work_orders.transition`，仅产生审批队列，不自动执行业务写操作。</span>
        </div>
      </div>
      <form class="approval-demo-form" @submit.prevent="generateApprovalRequest">
        <label>
          <span>工单 ID</span>
          <input v-model="demoForm.work_order_id" placeholder="WO-DEMO-P002-001" />
        </label>
        <label>
          <span>项目 ID</span>
          <input v-model="demoForm.project_id" placeholder="P002" />
        </label>
        <label>
          <span>建议动作</span>
          <select v-model="demoForm.action">
            <option value="confirm">confirm（审批派发）</option>
            <option value="accept">accept（分包接单）</option>
          </select>
        </label>
        <label class="form-wide">
          <span>Agent 消息</span>
          <input v-model="demoForm.message" />
        </label>
        <button class="action-button action-primary" type="submit" :disabled="generating || props.backendOnline === false">
          <Zap :size="16" />
          {{ generating ? '生成中' : '生成审批单' }}
        </button>
      </form>
    </section>

    <section class="panel panel-wide approval-toolbar">
      <label class="filter-chip">
        <span>状态筛选</span>
        <select v-model="statusFilter">
          <option value="pending">待审批</option>
          <option value="approved">已批准</option>
          <option value="executed">已执行</option>
          <option value="rejected">已驳回</option>
          <option value="execution_failed">执行失败</option>
          <option value="">全部</option>
        </select>
      </label>
      <span class="form-help">批准/驳回只改确认单状态；执行入口仅在 `approved + work_orders.transition` 时可用。</span>
    </section>

    <div v-if="errorMessage" class="notice notice-error panel-wide">
      <AlertCircle :size="16" />
      <span>{{ errorMessage }}</span>
    </div>
    <div v-if="successMessage" class="notice notice-success panel-wide">
      <CheckCircle2 :size="16" />
      <span>{{ successMessage }}</span>
    </div>

    <section class="panel panel-wide approval-board">
      <div v-if="loading" class="loading-panel">加载审批队列…</div>
      <template v-else-if="items.length">
        <div class="approval-list">
          <div
            v-for="item in items"
            :key="item.approval_id"
            class="rule-card"
            :class="{ 'is-selected': selected?.approval_id === item.approval_id }"
            @click="openDetail(item.approval_id)"
          >
            <div class="rule-card-head">
              <code class="metric-code">{{ item.approval_id }}</code>
              <span class="status-chip" :class="approvalStatusClass(item.status)">
                {{ approvalStatusLabel(item.status) }}
              </span>
            </div>
            <strong>{{ item.payload_summary || item.requested_tool }}</strong>
            <small>{{ item.project_id || '—' }} · {{ item.target_id || '—' }} · {{ item.requested_tool }}</small>
            <span class="rule-time">{{ formatTime(item.created_at) }}</span>
          </div>
        </div>

        <aside class="approval-detail" v-if="selected">
          <div class="detail-head">
            <div>
              <p class="eyebrow">{{ selected.approval_id }}</p>
              <h3>{{ selected.requested_tool }}</h3>
            </div>
            <span class="status-chip" :class="approvalStatusClass(selected.status)">
              {{ approvalStatusLabel(selected.status) }}
            </span>
          </div>

          <div class="detail-grid">
            <span>项目</span><strong>{{ selected.project_id || '—' }}</strong>
            <span>目标</span><strong>{{ selected.target_type }} / {{ selected.target_id || '—' }}</strong>
            <span>风险级别</span><strong>{{ selected.risk_level || '—' }}</strong>
            <span>请求人</span><strong>{{ selected.request_user_id || '—' }}</strong>
            <span>创建时间</span><strong>{{ formatTime(selected.created_at) }}</strong>
            <span>审批人</span><strong>{{ selected.approver_user_id || '—' }}</strong>
          </div>

          <p class="detail-description">{{ selected.reason || '无附加原因' }}</p>

          <div class="action-panel">
            <div class="panel-head compact">
              <h3>人工处理</h3>
              <span>2.4-H：前端对接 approve / reject / execute</span>
            </div>
            <label class="form-wide">
              <span>审批意见</span>
              <input v-model="decisionComment" placeholder="填写批准或驳回说明" />
            </label>
            <div class="work-order-actions">
              <button
                v-if="canApprove(selected.status)"
                class="action-button action-success"
                type="button"
                :disabled="acting"
                @click="approveSelected"
              >
                <CheckCircle2 :size="15" />
                批准
              </button>
              <button
                v-if="canApprove(selected.status)"
                class="action-button action-danger"
                type="button"
                :disabled="acting"
                @click="rejectSelected"
              >
                <XCircle :size="15" />
                驳回
              </button>
              <button
                v-if="canExecute(selected.status, selected.requested_tool)"
                class="action-button action-primary"
                type="button"
                :disabled="acting"
                @click="executeSelected"
              >
                <Play :size="15" />
                {{ acting ? '执行中' : '执行工单流转' }}
              </button>
            </div>
            <p v-if="!canApprove(selected.status) && !canExecute(selected.status, selected.requested_tool)" class="muted-text">
              当前状态无需操作，或该工具类型不在 2.4-G 可执行范围内。
            </p>
          </div>

          <div class="detail-section">
            <h3>载荷摘要</h3>
            <pre class="evidence-block">{{ formatJson(selected.payload_json) }}</pre>
          </div>

          <div v-if="selected.execution_result || selected.execution_error" class="detail-section governance-card">
            <h3>
              <ClipboardCheck :size="16" style="vertical-align: -2px; margin-right: 6px" />
              执行结果
            </h3>
            <pre v-if="selected.execution_result" class="evidence-block">{{ formatJson(selected.execution_result) }}</pre>
            <p v-if="selected.execution_error" class="notice notice-error">{{ selected.execution_error }}</p>
          </div>

          <AgentFeedbackBar
            :task-id="selected.run_id || selected.approval_id"
            agent-name="work_order_coordinator"
            :project-id="selected.project_id"
            :original-output="{
              approval_id: selected.approval_id,
              requested_tool: selected.requested_tool,
              status: selected.status,
              execution_result: selected.execution_result,
            }"
            :related-work-order-id="(selected.target_id as string | undefined) ?? undefined"
          />

          <div class="detail-section">
            <h3>
              <ShieldCheck :size="16" style="vertical-align: -2px; margin-right: 6px" />
              治理说明
            </h3>
            <p class="form-help">
              Agent 不自动创建处罚、停工或清退类工单。写操作必须先进入审批队列，由人工批准后再点击执行。
            </p>
          </div>
        </aside>
      </template>
      <p v-else class="empty-state">
        {{ statusFilter === 'pending' ? '暂无待审批单据，可用上方演示表单生成。' : '当前筛选下无记录。' }}
      </p>
    </section>
  </section>
</template>
