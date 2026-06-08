<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

import { useScopeContext } from '../composables/useScopeContext'
import { dashboardRouteForScope } from '../scopeView'

const router = useRouter()
const { currentUser } = useScopeContext()

onMounted(() => {
  router.replace(dashboardRouteForScope(currentUser.value.scope_type))
})
</script>

<template>
  <section class="page-grid">
    <div class="loading-panel">正在进入驾驶舱…</div>
  </section>
</template>
