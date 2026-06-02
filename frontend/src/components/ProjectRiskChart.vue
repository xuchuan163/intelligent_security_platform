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

function renderChart() {
  if (!chartEl.value) return
  chart ??= echarts.init(chartEl.value)
  chart.setOption({
    grid: { left: 34, right: 16, top: 22, bottom: 28 },
    xAxis: { type: 'category', data: props.items.map((item) => item.project_name), axisLabel: { interval: 0, rotate: 16 } },
    yAxis: { type: 'value', max: 100 },
    tooltip: { trigger: 'axis' },
    series: [
      {
        type: 'bar',
        data: props.items.map((item) => item.total_risk_score),
        itemStyle: {
          color: (params: { value: number }) => {
            if (params.value >= 81) return '#c2410c'
            if (params.value >= 61) return '#e0792b'
            if (params.value >= 31) return '#d6a01d'
            return '#2f8f5b'
          },
        },
        barWidth: 32,
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
