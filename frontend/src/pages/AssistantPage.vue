<script setup lang="ts">
import { Bot, Send } from 'lucide-vue-next'
import { ref } from 'vue'

import { api } from '../api/client'

const message = ref('为什么 P001 项目本周风险较高？')
const answer = ref('请输入安全管理问题，助手会基于结构化事实、规则命中和证据摘要输出解释。')
const loading = ref(false)

async function ask() {
  loading.value = true
  try {
    const result = await api.assistantChat(message.value, { project_id: 'P001', scope: 'demo' })
    answer.value = result.available ? (result.content ?? result.message) : result.message
  } catch {
    answer.value = '后端暂不可用。强规则和画像页面仍可用于安全管控判断。'
  } finally {
    loading.value = false
  }
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
        <Bot :size="22" />
        <p>{{ answer }}</p>
      </div>
      <div class="assistant-input">
        <input v-model="message" @keyup.enter="ask" />
        <button :disabled="loading" @click="ask" title="发送问题">
          <Send :size="17" />
          <span>{{ loading ? '发送中' : '发送' }}</span>
        </button>
      </div>
    </section>
    <section class="panel">
      <h3>治理边界</h3>
      <p>助手不能覆盖强规则结论，涉及停工、限制作业、处罚和清退时必须人工复核。</p>
    </section>
  </section>
</template>
