<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { api } from '../api/client'
import type { WorkOrder } from '../types/api'

const orders = ref<WorkOrder[]>([])
const loading = ref(true)

onMounted(async () => {
  try {
    orders.value = await api.workOrders()
  } catch {
    // fallback empty
  } finally {
    loading.value = false
  }
})

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    pending_confirm: '待确认',
    dispatched: '已派发',
    processing: '执行中',
    waiting_review: '待复查',
    closed: '已闭环',
    rejected: '已驳回',
    overdue_escalated: '超期升级',
  }
  return labels[status] ?? status
}
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Work Orders / {{ loading ? '加载中' : orders.length + ' 条' }}</p>
        <h2>隐患整改工单闭环</h2>
      </div>
    </div>
    <section class="panel panel-wide">
      <table class="data-table" v-if="!loading && orders.length > 0">
        <thead>
          <tr>
            <th>工单</th>
            <th>项目</th>
            <th>类型</th>
            <th>状态</th>
            <th>责任单位</th>
            <th>截止</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="order in orders" :key="order.work_order_id">
            <td>
              <strong>{{ order.title }}</strong>
              <small>{{ order.work_order_id }}</small>
            </td>
            <td>{{ order.project_name || order.project_id }}</td>
            <td><span class="status-chip">{{ order.work_order_type }}</span></td>
            <td><span class="status-chip">{{ statusLabel(order.status) }}</span></td>
            <td>{{ order.subcontractor_id || '-' }}</td>
            <td>{{ order.due_time?.slice(0, 10) || '-' }}</td>
          </tr>
        </tbody>
      </table>
      <p v-else style="padding:16px;color:var(--muted)">
        {{ loading ? '加载中...' : '暂无工单数据' }}
      </p>
    </section>
  </section>
</template>
