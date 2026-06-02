<script setup lang="ts">
import type { RiskLevel } from '../types/api'

const props = defineProps<{ level: RiskLevel | string }>()

const labels: Record<string, string> = {
  low: '低风险',
  medium: '中风险',
  high: '高风险',
  critical: '极高风险',
}
</script>

<template>
  <span class="risk-badge" :class="`risk-${props.level}`">{{ labels[props.level] ?? props.level }}</span>
</template>
