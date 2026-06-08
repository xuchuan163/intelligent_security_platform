<script setup lang="ts">
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { onMounted, onUnmounted, ref, watch } from 'vue'

import type { ProjectRankingItem } from '../types/api'

const props = defineProps<{ items: ProjectRankingItem[] }>()
const chartEl = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const riskColor = (value: number) => {
  if (value >= 81) return '#991b1b'
  if (value >= 61) return '#c2410c'
  if (value >= 31) return '#c9920a'
  return '#15803d'
}

function renderChart() {
  if (!chartEl.value) return
  chart ??= echarts.init(chartEl.value)
  chart.setOption({
    grid: { left: 40, right: 20, top: 28, bottom: 48 },
    xAxis: {
      type: 'category',
      data: props.items.map((item) => item.project_name),
      axisLabel: { interval: 0, rotate: 18, color: '#64748b', fontSize: 11 },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
    },
    yAxis: {
      type: 'value',
      max: 100,
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
      axisLabel: { color: '#94a3b8' },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(15, 23, 42, 0.92)',
      borderColor: 'transparent',
      textStyle: { color: '#f8fafc' },
    },
    series: [
      {
        type: 'bar',
        data: props.items.map((item) => ({
          value: item.total_risk_score,
          itemStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: riskColor(item.total_risk_score) },
              { offset: 1, color: `${riskColor(item.total_risk_score)}99` },
            ]),
            borderRadius: [6, 6, 0, 0],
          },
        })),
        barWidth: 36,
      },
    ],
  })
}

onMounted(renderChart)
watch(() => props.items, renderChart, { deep: true })
onUnmounted(() => chart?.dispose())
</script>

<template>
  <div ref="chartEl" class="risk-chart" />
</template>
