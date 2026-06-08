import { onMounted, ref } from 'vue'

import { api } from '../api/client'

export type BackendStatus = 'checking' | 'online' | 'offline'

export function useBackendHealth() {
  const status = ref<BackendStatus>('checking')
  const lastChecked = ref<Date | null>(null)

  async function check() {
    status.value = 'checking'
    try {
      await api.health()
      status.value = 'online'
    } catch {
      status.value = 'offline'
    } finally {
      lastChecked.value = new Date()
    }
  }

  onMounted(check)

  return { status, lastChecked, check }
}
