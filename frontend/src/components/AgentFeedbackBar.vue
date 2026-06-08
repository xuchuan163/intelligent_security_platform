<script setup lang="ts">
import { MessageSquare, ThumbsDown, ThumbsUp } from 'lucide-vue-next'
import { ref } from 'vue'

import { api } from '../api/client'

const props = defineProps<{
  taskId: string
  agentName: string
  projectId?: string | null
  originalOutput?: Record<string, unknown> | null
  relatedWorkOrderId?: string | null
}>()

const submitting = ref(false)
const submitted = ref(false)
const errorMessage = ref('')
const showCorrection = ref(false)
const correctionText = ref('')

async function submitThumb(rating: 1 | -1) {
  if (!props.taskId || submitting.value || submitted.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await api.submitAgentFeedback({
      task_id: props.taskId,
      agent_name: props.agentName,
      feedback_type: 'thumb',
      rating,
      feedback_reason: rating === 1 ? 'helpful' : 'not_helpful',
      original_output: props.originalOutput ?? undefined,
      project_id: props.projectId ?? undefined,
      related_work_order_id: props.relatedWorkOrderId ?? undefined,
    })
    submitted.value = true
  } catch {
    errorMessage.value = '反馈提交失败'
  } finally {
    submitting.value = false
  }
}

async function submitCorrection() {
  if (!correctionText.value.trim() || submitting.value) return
  submitting.value = true
  errorMessage.value = ''
  try {
    await api.submitAgentFeedback({
      task_id: props.taskId,
      agent_name: props.agentName,
      feedback_type: 'correction',
      correction_text: correctionText.value.trim(),
      original_output: props.originalOutput ?? undefined,
      project_id: props.projectId ?? undefined,
      related_work_order_id: props.relatedWorkOrderId ?? undefined,
    })
    submitted.value = true
    showCorrection.value = false
  } catch {
    errorMessage.value = '修正反馈提交失败'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="feedback-bar">
    <span class="feedback-label">
      <MessageSquare :size="14" />
      Agent 输出反馈
    </span>
    <div class="feedback-actions">
      <button type="button" class="action-button" :disabled="submitting || submitted" @click="submitThumb(1)">
        <ThumbsUp :size="14" />
        有帮助
      </button>
      <button type="button" class="action-button" :disabled="submitting || submitted" @click="submitThumb(-1)">
        <ThumbsDown :size="14" />
        需改进
      </button>
      <button type="button" class="action-button" :disabled="submitting || submitted" @click="showCorrection = !showCorrection">
        提交修正
      </button>
    </div>
    <p v-if="submitted" class="empty-state">感谢反馈，已记录为待标注样本。</p>
    <p v-if="errorMessage" class="empty-state">{{ errorMessage }}</p>
    <div v-if="showCorrection && !submitted" class="feedback-correction">
      <textarea v-model="correctionText" rows="2" placeholder="描述应如何修正 Agent 输出…" />
      <button type="button" class="action-button action-primary" :disabled="submitting" @click="submitCorrection">
        提交修正说明
      </button>
    </div>
  </div>
</template>
