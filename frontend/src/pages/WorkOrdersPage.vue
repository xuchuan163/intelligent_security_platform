<script setup lang="ts">
import {
  AlertCircle,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Eye,
  FileImage,
  Play,
  RotateCcw,
  Send,
  ShieldCheck,
  Upload,
} from 'lucide-vue-next'
import { computed, onMounted, reactive, ref, watch } from 'vue'

import { api } from '../api/client'
import { useScopeContext } from '../composables/useScopeContext'
import {
  buildHazardUploadFormData,
  validateHazardUploadDraft,
  type HazardLevel,
  type HazardUploadDraft,
} from '../hazardUploadForm'
import type {
  CurrentUser,
  WorkOrder,
  WorkOrderAttachment,
  WorkOrderAttachmentEnvelope,
  WorkOrderCreatePayload,
  WorkOrderDetail,
  WorkOrderStatusPayload,
} from '../types/api'
import { availableWorkOrderActions, statusLabel, type WorkOrderActionItem } from '../workOrderFlow'

const props = defineProps<{
  currentUser?: CurrentUser | null
}>()

const { projectFilter } = useScopeContext()

const orders = ref<WorkOrder[]>([])
const selectedOrder = ref<WorkOrderDetail | null>(null)
const loading = ref(true)
const detailLoading = ref(false)
const actingOrderId = ref<string | null>(null)
const creating = ref(false)
const hazardSubmitting = ref(false)
const errorMessage = ref('')
const successMessage = ref('')
const rectificationFile = ref<File | null>(null)
const hazardImages = ref<File[]>([])
const demoActorId = ref('gc')

const demoActors = [
  {
    id: 'gc',
    label: '总包安全员',
    userId: 'U-GC-01',
    userName: '李安全',
    role: 'gc_safety_officer',
    subcontractorId: null,
  },
  {
    id: 'director',
    label: '安全总监',
    userId: 'U-DIR-01',
    userName: '王总监',
    role: 'safety_director',
    subcontractorId: null,
  },
  {
    id: 'sub',
    label: '分包安全员',
    userId: 'U-SUB-S003',
    userName: '陈分包',
    role: 'sub_safety_officer',
    subcontractorId: 'S003',
  },
]

const hazardForm = reactive({
  project_id: 'P002',
  description: '',
  hazard_type: 'edge_protection',
  hazard_level: 'general' as HazardLevel,
  subcontractor_id: 'S003',
  due_date: defaultDueDate(),
  location: '',
})

const createForm = reactive({
  title: '',
  project_id: 'P002',
  work_order_type: 'hazard_rectification',
  priority: 'normal',
  description: '',
})

const actionForm = reactive({
  assignee_user_id: 'U-SUB-S003',
  due_time: '',
  comment: '',
  reject_reason: '',
})

const selectedDemoActor = computed(() => demoActors.find((actor) => actor.id === demoActorId.value) ?? demoActors[0])
const currentRole = computed(() => selectedDemoActor.value.role || props.currentUser?.role || '')
const canUploadHazard = computed(() => currentRole.value === 'gc_safety_officer')
const openOrderCount = computed(() => orders.value.filter((order) => order.status !== 'closed').length)
const waitingReviewCount = computed(() => orders.value.filter((order) => order.status === 'waiting_review').length)
const detailActions = computed(() =>
  selectedOrder.value ? availableWorkOrderActions(selectedOrder.value.status, currentRole.value) : [],
)
const selectedAttachments = computed(() => flattenAttachments(selectedOrder.value?.attachments))

onMounted(async () => {
  applyDemoActor()
  await loadOrders()
})

async function changeDemoActor() {
  applyDemoActor()
  await loadOrders()
  if (selectedOrder.value) {
    await openDetail(selectedOrder.value.work_order_id)
  }
}

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

async function loadOrders() {
  loading.value = true
  errorMessage.value = ''
  try {
    const params = projectFilter.value ? { project_id: projectFilter.value } : undefined
    orders.value = await api.workOrders(params)
    if (!selectedOrder.value && orders.value.length > 0) {
      await openDetail(orders.value[0].work_order_id)
    }
  } catch (error) {
    errorMessage.value = '工单数据加载失败，请检查后端服务。'
  } finally {
    loading.value = false
  }
}

watch(projectFilter, loadOrders)

async function openDetail(workOrderId: string) {
  detailLoading.value = true
  errorMessage.value = ''
  try {
    selectedOrder.value = await api.workOrderDetail(workOrderId)
    seedActionDefaults(selectedOrder.value)
  } catch (error) {
    errorMessage.value = `${workOrderId} 详情加载失败，请确认当前账号是否有项目权限。`
  } finally {
    detailLoading.value = false
  }
}

async function uploadHazard() {
  if (!canUploadHazard.value) {
    errorMessage.value = '只有总包安全员可以上传隐患。'
    return
  }

  const draft = hazardDraft()
  const validationError = validateHazardUploadDraft(draft)
  if (validationError) {
    errorMessage.value = validationError
    return
  }

  hazardSubmitting.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const result = await api.createProjectHazard(draft.projectId, buildHazardUploadFormData(draft))
    successMessage.value = `隐患 ${result.hazard_id} 上传成功，已自动创建工单 ${result.work_order_id}`
    resetHazardForm()
    await loadOrders()
    await openDetail(result.work_order_id)
  } catch (error) {
    errorMessage.value = '隐患上传失败，请检查图片、项目权限和必填字段。'
  } finally {
    hazardSubmitting.value = false
  }
}

function hazardDraft(): HazardUploadDraft {
  return {
    projectId: hazardForm.project_id,
    description: hazardForm.description,
    hazardType: hazardForm.hazard_type,
    hazardLevel: hazardForm.hazard_level,
    subcontractorId: hazardForm.subcontractor_id,
    dueDate: hazardForm.due_date,
    location: hazardForm.location,
    images: hazardImages.value,
  }
}

function resetHazardForm() {
  hazardForm.description = ''
  hazardForm.location = ''
  hazardForm.hazard_level = 'general'
  hazardForm.hazard_type = 'edge_protection'
  hazardForm.due_date = defaultDueDate()
  hazardImages.value = []
}

async function refreshAfterAction(workOrderId: string, newStatus: string) {
  const target = orders.value.find((order) => order.work_order_id === workOrderId)
  if (target) {
    target.status = newStatus
  }
  await openDetail(workOrderId)
  await loadOrders()
}

async function applyAction(item: WorkOrderActionItem) {
  if (!selectedOrder.value) {
    return
  }

  actingOrderId.value = selectedOrder.value.work_order_id
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const result =
      item.action === 'submit_result'
        ? await submitRectification(selectedOrder.value.work_order_id)
        : await api.updateWorkOrderStatus(selectedOrder.value.work_order_id, buildStatusPayload(item.action))

    successMessage.value = `${result.work_order_id} 已更新为${statusLabel(result.new_status)}`
    resetActionInputs(item.action)
    await refreshAfterAction(result.work_order_id, result.new_status)
  } catch (error) {
    errorMessage.value = actionErrorMessage(item)
  } finally {
    actingOrderId.value = null
  }
}

async function submitRectification(workOrderId: string) {
  if (!rectificationFile.value) {
    throw new Error('rectification image required')
  }

  const body = new FormData()
  body.append('action', 'submit_result')
  body.append('comment', actionForm.comment.trim() || '已完成整改，提交验收。')
  body.append('images', rectificationFile.value)
  return api.submitRectification(workOrderId, body)
}

function buildStatusPayload(action: string): WorkOrderStatusPayload {
  const payload: WorkOrderStatusPayload = {
    action,
    comment: actionForm.comment.trim() || null,
  }

  if (action === 'confirm') {
    payload.assignee_user_id = actionForm.assignee_user_id.trim() || null
    payload.due_time = actionForm.due_time || null
  }
  if (action === 'review_reject') {
    payload.reject_reason = actionForm.reject_reason.trim() || '整改结果未满足验收要求。'
  }
  return payload
}

async function createOrder() {
  if (!createForm.title.trim()) {
    errorMessage.value = '请填写工单标题。'
    return
  }

  creating.value = true
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const payload: WorkOrderCreatePayload = {
      title: createForm.title.trim(),
      project_id: createForm.project_id.trim() || null,
      work_order_type: createForm.work_order_type,
      priority: createForm.priority,
      description: createForm.description.trim() || null,
    }
    const result = await api.createWorkOrder(payload)
    successMessage.value = `工单 ${result.work_order_id} 创建成功`
    createForm.title = ''
    createForm.description = ''
    await loadOrders()
    await openDetail(result.work_order_id)
  } catch (error) {
    errorMessage.value = '工单创建失败，请检查项目 ID 和必填字段。'
  } finally {
    creating.value = false
  }
}

function seedActionDefaults(order: WorkOrderDetail) {
  actionForm.assignee_user_id = order.responsible_user_id || actionForm.assignee_user_id || 'U-SUB-S003'
  if (!actionForm.due_time) {
    const due = new Date(Date.now() + 72 * 60 * 60 * 1000)
    actionForm.due_time = due.toISOString().slice(0, 16)
  }
}

function resetActionInputs(action: string) {
  actionForm.comment = ''
  if (action === 'review_reject') {
    actionForm.reject_reason = ''
  }
  if (action === 'submit_result') {
    rectificationFile.value = null
  }
}

function onRectificationFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  rectificationFile.value = input.files?.[0] ?? null
}

function onHazardImagesChange(event: Event) {
  const input = event.target as HTMLInputElement
  hazardImages.value = Array.from(input.files ?? [])
}

function flattenAttachments(envelope?: WorkOrderAttachmentEnvelope | null): WorkOrderAttachment[] {
  return envelope?.items ?? []
}

function flowAttachments(envelope?: WorkOrderAttachmentEnvelope | null): WorkOrderAttachment[] {
  return envelope?.items ?? []
}

function attachmentHref(attachment: WorkOrderAttachment): string {
  return attachment.url || api.fileUrl(attachment.file_id)
}

function actionIcon(action: string) {
  const icons = {
    confirm: Send,
    accept: Play,
    submit_result: ClipboardCheck,
    review_pass: CheckCircle2,
    review_reject: RotateCcw,
  }
  return icons[action as keyof typeof icons] ?? ShieldCheck
}

function priorityLabel(priority: string): string {
  const labels: Record<string, string> = {
    low: '低',
    normal: '普通',
    high: '高',
    urgent: '紧急',
  }
  return labels[priority] ?? priority
}

function actionHint(action: string): string {
  const hints: Record<string, string> = {
    confirm: '安全总监审批后派发给分包安全员，需填写处理人和截止时间。',
    accept: '分包安全员确认接单，工单进入整改中。',
    submit_result: '上传整改后图片并填写说明，提交给总包验收。',
    review_pass: '总包安全员验收通过，工单闭环。',
    review_reject: '总包安全员驳回后，分包继续整改。',
  }
  return hints[action] ?? ''
}

function actionErrorMessage(item: WorkOrderActionItem): string {
  if (item.action === 'submit_result' && !rectificationFile.value) {
    return '提交整改必须上传一张整改图片。'
  }
  return `${item.label}失败，请确认当前账号岗位、工单状态和项目权限。`
}

function defaultDueDate(): string {
  const due = new Date(Date.now() + 3 * 24 * 60 * 60 * 1000)
  return due.toISOString().slice(0, 10)
}
</script>

<template>
  <section class="page-grid work-order-page">
    <div class="page-title">
      <div>
        <p class="eyebrow">Work Orders / {{ loading ? '加载中' : orders.length + ' 条' }}</p>
        <h2>隐患上传与工单闭环</h2>
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
        <span>当前岗位：{{ currentRole || '未识别' }}</span>
        <span>未闭环 {{ openOrderCount }}</span>
        <span>待验收 {{ waitingReviewCount }}</span>
      </div>
    </div>

    <section class="panel panel-wide hazard-upload-panel">
      <div class="panel-head">
        <div>
          <p class="eyebrow">Hazard Intake</p>
          <h3>隐患上传</h3>
          <span>总包安全员上传图片和文字描述后，系统自动创建隐患和待确认工单。</span>
        </div>
        <span class="status-chip" :class="canUploadHazard ? 'status-processing' : 'status-closed'">
          {{ canUploadHazard ? '可上传' : '切换到总包安全员' }}
        </span>
      </div>
      <form class="hazard-upload-form" @submit.prevent="uploadHazard">
        <label>
          <span>项目 ID</span>
          <input v-model="hazardForm.project_id" :disabled="!canUploadHazard" placeholder="P002" />
        </label>
        <label>
          <span>责任分包</span>
          <input v-model="hazardForm.subcontractor_id" :disabled="!canUploadHazard" placeholder="S003" />
        </label>
        <label>
          <span>隐患类型</span>
          <select v-model="hazardForm.hazard_type" :disabled="!canUploadHazard">
            <option value="edge_protection">临边防护</option>
            <option value="scaffold">脚手架</option>
            <option value="temporary_electricity">临时用电</option>
            <option value="fire_safety">消防安全</option>
            <option value="lifting">起重吊装</option>
          </select>
        </label>
        <label>
          <span>隐患等级</span>
          <select v-model="hazardForm.hazard_level" :disabled="!canUploadHazard">
            <option value="general">一般隐患</option>
            <option value="major">重大隐患</option>
          </select>
        </label>
        <label>
          <span>整改期限</span>
          <input v-model="hazardForm.due_date" :disabled="!canUploadHazard" type="date" />
        </label>
        <label>
          <span>位置</span>
          <input v-model="hazardForm.location" :disabled="!canUploadHazard" placeholder="例如：2号楼3层西侧" />
        </label>
        <label class="form-wide">
          <span>文字描述</span>
          <textarea
            v-model="hazardForm.description"
            :disabled="!canUploadHazard"
            rows="3"
            placeholder="描述隐患事实、位置、风险和整改要求，至少 10 个字"
          />
        </label>
        <label class="file-uploader">
          <Camera :size="18" />
          <span>{{ hazardImages.length ? `已选择 ${hazardImages.length} 张图片` : '上传隐患图片' }}</span>
          <input :disabled="!canUploadHazard" type="file" accept="image/*" multiple @change="onHazardImagesChange" />
        </label>
        <button class="action-button action-primary" type="submit" :disabled="!canUploadHazard || hazardSubmitting">
          <Upload :size="16" />
          {{ hazardSubmitting ? '上传中' : '上传并建单' }}
        </button>
      </form>
      <p class="form-help">
        固定范式：图片 + 文字描述。上传成功后工单进入待确认，由安全总监继续审批派发。
      </p>
    </section>

    <section class="panel panel-wide work-order-create">
      <div class="panel-head">
        <div>
          <h3>手工补录工单</h3>
          <span>用于非隐患上传来源的整改任务补录。</span>
        </div>
      </div>
      <form class="work-order-form" @submit.prevent="createOrder">
        <label>
          <span>标题</span>
          <input v-model="createForm.title" placeholder="例如：临边防护缺失整改" />
        </label>
        <label>
          <span>项目 ID</span>
          <input v-model="createForm.project_id" placeholder="P002" />
        </label>
        <label>
          <span>类型</span>
          <select v-model="createForm.work_order_type">
            <option value="hazard_rectification">隐患整改</option>
            <option value="equipment_inspection">设备检查</option>
            <option value="worker_training">人员培训</option>
            <option value="safety_training">安全教育</option>
          </select>
        </label>
        <label>
          <span>优先级</span>
          <select v-model="createForm.priority">
            <option value="normal">普通</option>
            <option value="high">高</option>
            <option value="urgent">紧急</option>
            <option value="low">低</option>
          </select>
        </label>
        <label class="form-wide">
          <span>描述</span>
          <input v-model="createForm.description" placeholder="补充整改要求、位置或责任说明" />
        </label>
        <button class="action-button action-primary" type="submit" :disabled="creating">
          <ShieldCheck :size="16" />
          {{ creating ? '创建中' : '创建工单' }}
        </button>
      </form>
    </section>

    <section class="panel panel-wide">
      <div v-if="errorMessage" class="notice notice-error">
        <AlertCircle :size="16" />
        <span>{{ errorMessage }}</span>
      </div>
      <div v-if="successMessage" class="notice notice-success">
        <CheckCircle2 :size="16" />
        <span>{{ successMessage }}</span>
      </div>

      <div class="work-order-board" v-if="!loading && orders.length > 0">
        <div class="work-order-list">
          <table class="data-table work-order-table">
            <thead>
              <tr>
                <th>工单</th>
                <th>项目</th>
                <th>状态</th>
                <th>责任单位</th>
                <th>截止</th>
                <th>详情</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="order in orders"
                :key="order.work_order_id"
                :class="{ 'is-selected': selectedOrder?.work_order_id === order.work_order_id }"
              >
                <td data-label="工单">
                  <strong>{{ order.title || '未命名工单' }}</strong>
                  <small>{{ order.work_order_id }}</small>
                </td>
                <td data-label="项目">{{ order.project_name || order.project_id || '-' }}</td>
                <td data-label="状态">
                  <span class="status-chip" :class="`status-${order.status}`">{{ statusLabel(order.status) }}</span>
                </td>
                <td data-label="责任单位">{{ order.subcontractor_id || '-' }}</td>
                <td data-label="截止">{{ order.due_time?.slice(0, 10) || '-' }}</td>
                <td data-label="详情">
                  <button class="icon-button" type="button" title="查看详情" @click="openDetail(order.work_order_id)">
                    <Eye :size="16" />
                  </button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <aside class="work-order-detail">
          <p v-if="detailLoading" class="empty-state">详情加载中...</p>
          <template v-else-if="selectedOrder">
            <div class="detail-head">
              <div>
                <p class="eyebrow">{{ selectedOrder.work_order_id }}</p>
                <h3>{{ selectedOrder.title || '未命名工单' }}</h3>
              </div>
              <span class="status-chip" :class="`status-${selectedOrder.status}`">
                {{ statusLabel(selectedOrder.status) }}
              </span>
            </div>

            <div class="detail-grid">
              <span>项目</span>
              <strong>{{ selectedOrder.project_id || '-' }}</strong>
              <span>责任分包</span>
              <strong>{{ selectedOrder.subcontractor_id || '-' }}</strong>
              <span>处理人</span>
              <strong>{{ selectedOrder.responsible_user_id || '-' }}</strong>
              <span>截止时间</span>
              <strong>{{ selectedOrder.due_time?.replace('T', ' ').slice(0, 16) || '-' }}</strong>
            </div>

            <p class="detail-description">{{ selectedOrder.description || '暂无描述' }}</p>

            <div class="action-panel">
              <div class="panel-head compact">
                <div>
                  <h3>岗位动作</h3>
                  <span>只显示当前账号可执行的状态流转。</span>
                </div>
              </div>

              <div v-if="detailActions.length" class="action-fields">
                <label v-if="detailActions.some((item) => item.action === 'confirm')">
                  <span>分包安全员用户 ID</span>
                  <input v-model="actionForm.assignee_user_id" placeholder="U-SUB-S003" />
                </label>
                <label v-if="detailActions.some((item) => item.action === 'confirm')">
                  <span>整改截止时间</span>
                  <input v-model="actionForm.due_time" type="datetime-local" />
                </label>
                <label v-if="detailActions.some((item) => item.action === 'submit_result')">
                  <span>整改图片</span>
                  <input type="file" accept="image/*" @change="onRectificationFileChange" />
                </label>
                <label v-if="detailActions.some((item) => item.action === 'review_reject')">
                  <span>驳回原因</span>
                  <input v-model="actionForm.reject_reason" placeholder="说明未通过原因" />
                </label>
                <label class="form-wide">
                  <span>处理说明</span>
                  <input v-model="actionForm.comment" placeholder="填写审批、整改或验收说明" />
                </label>
              </div>
              <p v-else class="muted-text">当前岗位没有可执行动作，或工单已完成闭环。</p>

              <div class="work-order-actions" v-if="detailActions.length">
                <button
                  v-for="item in detailActions"
                  :key="item.action"
                  class="action-button"
                  :class="`action-${item.tone}`"
                  type="button"
                  :title="actionHint(item.action)"
                  :disabled="actingOrderId === selectedOrder.work_order_id"
                  @click="applyAction(item)"
                >
                  <component :is="actionIcon(item.action)" :size="15" />
                  {{ actingOrderId === selectedOrder.work_order_id ? '处理中' : item.label }}
                </button>
              </div>
            </div>

            <div class="detail-section">
              <h3>附件</h3>
              <div v-if="selectedAttachments.length" class="attachment-list">
                <a
                  v-for="attachment in selectedAttachments"
                  :key="attachment.file_id"
                  :href="attachmentHref(attachment)"
                  target="_blank"
                  rel="noreferrer"
                >
                  <FileImage :size="15" />
                  <span>{{ attachment.file_name || attachment.file_id }}</span>
                  <small>{{ attachment.phase || 'attachment' }}</small>
                </a>
              </div>
              <p v-else class="muted-text">暂无附件。</p>
            </div>

            <div class="detail-section">
              <h3>流转日志</h3>
              <div class="flow-list">
                <div v-for="log in selectedOrder.flow_logs" :key="`${log.action}-${log.created_at}`" class="flow-item">
                  <Clock3 :size="15" />
                  <div>
                    <strong>{{ statusLabel(log.from_status || '创建') }} -> {{ statusLabel(log.to_status) }}</strong>
                    <span>{{ log.operator_role }} / {{ log.operator_user_id }} / {{ log.created_at.replace('T', ' ').slice(0, 16) }}</span>
                    <p v-if="log.comment">{{ log.comment }}</p>
                    <p v-if="log.reject_reason">驳回原因：{{ log.reject_reason }}</p>
                    <div v-if="flowAttachments(log.attachments).length" class="flow-attachments">
                      <a
                        v-for="attachment in flowAttachments(log.attachments)"
                        :key="attachment.file_id"
                        :href="attachmentHref(attachment)"
                        target="_blank"
                        rel="noreferrer"
                      >
                        {{ attachment.file_name || attachment.file_id }}
                      </a>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </template>
          <p v-else class="empty-state">选择左侧工单查看详情。</p>
        </aside>
      </div>
      <p v-else class="empty-state">
        {{ loading ? '加载中...' : '暂无工单数据' }}
      </p>
    </section>
  </section>
</template>
