<script setup lang="ts">
import { AlertTriangle, ClipboardList, FolderKanban, TrendingUp } from 'lucide-vue-next'
import { computed, type Component } from 'vue'

const props = defineProps<{
  label: string
  value: string | number
  tone?: 'neutral' | 'warning' | 'danger' | 'good'
  icon?: 'folder' | 'alert' | 'clipboard' | 'trend'
}>()

const iconMap: Record<string, Component> = {
  folder: FolderKanban,
  alert: AlertTriangle,
  clipboard: ClipboardList,
  trend: TrendingUp,
}

const Icon = computed(() => (props.icon ? iconMap[props.icon] : null))
</script>

<template>
  <section class="stat-tile" :class="`tone-${tone ?? 'neutral'}`">
    <div class="stat-tile-head">
      <p>{{ label }}</p>
      <component v-if="Icon" :is="Icon" :size="18" class="stat-icon" />
    </div>
    <strong>{{ value }}</strong>
  </section>
</template>

<style scoped>
.stat-tile-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.stat-icon {
  color: var(--muted);
  opacity: 0.7;
}

.tone-danger .stat-icon {
  color: var(--danger);
  opacity: 0.85;
}

.tone-warning .stat-icon {
  color: var(--warning);
  opacity: 0.85;
}
</style>
