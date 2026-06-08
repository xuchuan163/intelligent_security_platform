<script setup lang="ts">
import { Bot, Send, ShieldCheck, Sparkles } from 'lucide-vue-next'
import { ref } from 'vue'

import { api } from '../api/client'

const suggestions = [
  '为什么 P001 项目本周风险较高？',
  'P002 有哪些强规则最近被触发？',
  '如何理解工人证书过期对风险分的影响？',
]

const message = ref(suggestions[0])
const answer = ref('请输入安全管理问题，助手会基于结构化事实、规则命中和证据摘要输出解释。')
const loading = ref(false)
const needReview = ref(false)

async function ask() {
  if (!message.value.trim()) return
  loading.value = true
  needReview.value = false
  try {
    const result = await api.assistantChat(message.value, { project_id: 'P001', scope: 'demo' })
    answer.value = result.available ? (result.content ?? result.message) : result.message
    needReview.value = Boolean(result.need_human_review)
  } catch {
    answer.value = '后端暂不可用。请先确认侧边栏 API 状态为「已连接」，强规则和画像页面仍可用于安全管控判断。'
  } finally {
    loading.value = false
  }
}

function useSuggestion(text: string) {
  message.value = text
  ask()
}
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Qwen-plus / Facts First</p>
        <h2>安全智能助手</h2>
      </div>
    </div>

    <section class="panel panel-wide assistant-panel">
      <div class="assistant-output">
        <Bot :size="24" />
        <div>
          <p>{{ answer }}</p>
          <span v-if="needReview" class="status-chip status-waiting_review" style="margin-top: 12px">
            需人工复核
          </span>
        </div>
      </div>

      <div class="suggestion-row">
        <Sparkles :size="15" />
        <button
          v-for="item in suggestions"
          :key="item"
          type="button"
          class="suggestion-chip"
          :disabled="loading"
          @click="useSuggestion(item)"
        >
          {{ item }}
        </button>
      </div>

      <div class="assistant-input">
        <input v-model="message" placeholder="描述你的安全管理问题…" @keyup.enter="ask" />
        <button :disabled="loading" @click="ask" title="发送问题">
          <Send :size="17" />
          <span>{{ loading ? '分析中' : '发送' }}</span>
        </button>
      </div>
    </section>

    <section class="panel governance-card">
      <h3>
        <ShieldCheck :size="18" style="vertical-align: -3px; margin-right: 6px" />
        治理边界
      </h3>
      <p>助手不能覆盖强规则结论，涉及停工、限制作业、处罚和清退时必须人工复核。</p>
    </section>
  </section>
</template>

<style scoped>
.suggestion-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--muted);
}

.suggestion-chip {
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-solid);
  color: var(--ink-soft);
  padding: 7px 12px;
  font-size: 12px;
  cursor: pointer;
  transition: border-color 0.15s ease, background 0.15s ease;
}

.suggestion-chip:hover:not(:disabled) {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.suggestion-chip:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
