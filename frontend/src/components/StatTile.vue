<script setup lang="ts">
defineProps<{
  label: string
  value: string | number
  tone?: 'neutral' | 'warning' | 'danger' | 'good'
}>()
</script>

<template>
  <section class="stat-tile" :class="`tone-${tone ?? 'neutral'}`">
    <p>{{ label }}</p>
    <strong>{{ value }}</strong>
  </section>
</template>
