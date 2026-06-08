<script setup lang="ts">
import { BookOpen, ChevronLeft, ChevronRight, Search } from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { api } from '../api/client'
import type { MetricCatalogItem, MetricDetail } from '../types/api'

const items = ref<MetricCatalogItem[]>([])
const selected = ref<MetricDetail | null>(null)
const selectedCode = ref<string | null>(null)
const loading = ref(true)
const detailLoading = ref(false)
const errorMessage = ref('')

const pageNo = ref(1)
const pageSize = ref(20)
const total = ref(0)
const keyword = ref('')
const statusFilter = ref('')

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize.value)))

onMounted(loadCatalog)
watch([pageNo, statusFilter], loadCatalog)

async function loadCatalog() {
  loading.value = true
  errorMessage.value = ''
  try {
    const result = await api.metricsCatalog({
      page_no: pageNo.value,
      page_size: pageSize.value,
      status: statusFilter.value || undefined,
      keyword: keyword.value.trim() || undefined,
    })
    items.value = result.items
    total.value = result.total
    if (!selectedCode.value && result.items.length > 0) {
      await openDetail(result.items[0].metric_code)
    }
  } catch {
    errorMessage.value = '指标目录加载失败，请确认后端已连接。'
    items.value = []
  } finally {
    loading.value = false
  }
}

async function search() {
  pageNo.value = 1
  await loadCatalog()
}

async function openDetail(metricCode: string) {
  selectedCode.value = metricCode
  detailLoading.value = true
  try {
    selected.value = await api.metricDetail(metricCode)
  } catch {
    selected.value = null
    errorMessage.value = `指标 ${metricCode} 详情加载失败。`
  } finally {
    detailLoading.value = false
  }
}

function formatJson(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}

function statusClass(status: string): string {
  return status === 'enabled' ? 'status-processing' : 'status-closed'
}
</script>

<template>
  <section class="page-grid">
    <div class="page-title">
      <div>
        <p class="eyebrow">Metrics / Semantic Layer</p>
        <h2>指标语义目录</h2>
      </div>
      <span class="status-pill">
        <BookOpen :size="14" />
        共 {{ total }} 条指标
      </span>
    </div>

    <section class="panel panel-wide catalog-toolbar">
      <div class="search-bar">
        <Search :size="18" />
        <input
          v-model="keyword"
          placeholder="搜索指标编码、名称或口径…"
          @keyup.enter="search"
        />
        <button type="button" class="action-button action-primary" @click="search">搜索</button>
      </div>
      <label class="filter-chip">
        <span>状态</span>
        <select v-model="statusFilter">
          <option value="">全部</option>
          <option value="enabled">启用</option>
          <option value="disabled">停用</option>
        </select>
      </label>
    </section>

    <div v-if="errorMessage" class="notice notice-error panel-wide">{{ errorMessage }}</div>

    <section class="panel panel-wide catalog-board">
      <div v-if="loading" class="loading-panel">加载指标目录…</div>
      <template v-else-if="items.length">
        <div class="catalog-list">
          <table class="data-table catalog-table">
            <thead>
              <tr>
                <th>编码</th>
                <th>名称</th>
                <th>周期</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in items"
                :key="item.metric_code"
                :class="{ 'is-selected': selectedCode === item.metric_code }"
                @click="openDetail(item.metric_code)"
              >
                <td><code class="metric-code">{{ item.metric_code }}</code></td>
                <td>
                  <strong>{{ item.metric_name }}</strong>
                  <small>{{ item.business_definition?.slice(0, 48) }}{{ (item.business_definition?.length ?? 0) > 48 ? '…' : '' }}</small>
                </td>
                <td>{{ item.statistical_period || '—' }}</td>
                <td>
                  <span class="status-chip" :class="statusClass(item.status)">{{ item.status }}</span>
                </td>
              </tr>
            </tbody>
          </table>

          <div class="pager">
            <button type="button" class="icon-button" :disabled="pageNo <= 1" @click="pageNo--">
              <ChevronLeft :size="16" />
            </button>
            <span>第 {{ pageNo }} / {{ totalPages }} 页</span>
            <button type="button" class="icon-button" :disabled="pageNo >= totalPages" @click="pageNo++">
              <ChevronRight :size="16" />
            </button>
          </div>
        </div>

        <aside class="catalog-detail">
          <p v-if="detailLoading" class="empty-state">加载详情…</p>
          <template v-else-if="selected">
            <div class="detail-head">
              <div>
                <p class="eyebrow">{{ selected.metric_code }}</p>
                <h3>{{ selected.metric_name }}</h3>
              </div>
              <span class="status-chip" :class="statusClass(selected.status)">{{ selected.status }}</span>
            </div>

            <div class="detail-grid">
              <span>版本</span><strong>{{ selected.metric_version }}</strong>
              <span>统计周期</span><strong>{{ selected.statistical_period || '—' }}</strong>
              <span>权限级别</span><strong>{{ selected.permission_level || '—' }}</strong>
              <span>责任部门</span><strong>{{ selected.owner_department || '—' }}</strong>
            </div>

            <div class="detail-section">
              <h3>业务口径</h3>
              <p>{{ selected.business_definition || '暂无定义' }}</p>
            </div>

            <div class="detail-section">
              <h3>计算公式</h3>
              <pre class="evidence-block">{{ selected.calculation_formula || '—' }}</pre>
            </div>

            <div class="detail-section" v-if="selected.aliases?.length">
              <h3>别名（NL2SQL）</h3>
              <div class="tag-row">
                <span v-for="alias in selected.aliases" :key="alias" class="risk-tag">{{ alias }}</span>
              </div>
            </div>

            <div class="detail-section">
              <h3>数据来源</h3>
              <pre class="evidence-block">{{ formatJson({ tables: selected.source_tables, fields: selected.source_fields, filters: selected.filters }) }}</pre>
            </div>
          </template>
          <p v-else class="empty-state">选择左侧指标查看详情</p>
        </aside>
      </template>
      <p v-else class="empty-state">暂无指标数据，请先执行 seed 脚本。</p>
    </section>
  </section>
</template>
