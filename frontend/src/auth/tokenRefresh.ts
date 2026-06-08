import { api } from '../api/client'
import { hasStoredSession, isJwtAuthMode } from './session'

let refreshTimer: ReturnType<typeof setInterval> | null = null

export function startTokenRefreshLoop(intervalMs = 30_000): void {
  stopTokenRefreshLoop()
  if (!isJwtAuthMode()) return

  const tick = () => {
    if (!hasStoredSession()) return
    void api.refreshSessionIfNeeded()
  }

  refreshTimer = setInterval(tick, intervalMs)
  void tick()
}

export function stopTokenRefreshLoop(): void {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
}
