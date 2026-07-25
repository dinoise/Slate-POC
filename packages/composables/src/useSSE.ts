import { ref, watch, onUnmounted, type Ref } from 'vue'
import { SSE, type SSEvent } from 'sse.js'
import type { AssignmentEvent } from '@slate/types'
import { getAuthToken, triggerUnauthorized } from '@slate/api-client'

export interface UseSSEReturn {
  events: Ref<AssignmentEvent[]>
  connected: Ref<boolean>
  error: Ref<string | null>
  disconnect: () => void
}

/**
 * Reactive SSE composable with exponential backoff reconnection.
 *
 * Uses sse.js instead of native EventSource so that:
 * - The auth token is sent as `Authorization: Bearer` header (not ?token= in URL)
 * - HTTP status codes are exposed in onerror via event.responseCode — 401/403
 *   triggers triggerUnauthorized() and stops reconnecting
 * - Works cross-browser (Firefox + Chromium) — sse.js uses XHR internally
 * - Network drops and 5xx errors reconnect with exponential backoff (1s → 60s)
 *
 * Watches `adjusterId` — when it changes the old connection is closed and a
 * new one is opened. If `adjusterId` becomes null the stream is disconnected.
 */
export function useSSE(adjusterId: Ref<number | null>): UseSSEReturn {
  const events = ref<AssignmentEvent[]>([])
  const connected = ref(false)
  const error = ref<string | null>(null)

  let source: SSE | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let backoff = 1000
  let connectedFor: number | null = null

  const notificationsUrl =
    (import.meta as ImportMeta & { env: { VITE_NOTIFICATIONS_URL?: string } }).env
      .VITE_NOTIFICATIONS_URL ?? ''

  function _close() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    source?.close()
    source = null
    connected.value = false
    connectedFor = null
    events.value = []
  }

  function connect() {
    const id = adjusterId.value
    if (!id) { _close(); return }

    _close()
    backoff = 1000
    connectedFor = id

    const token = getAuthToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`

    source = new SSE(`${notificationsUrl}/notifications/stream/adjusters/${id}`, {
      headers,
      autoReconnect: false,   // we handle reconnect with our own backoff timer
    })

    source.onopen = () => {
      connected.value = true
      error.value = null
      backoff = 1000
    }

    source.addEventListener('assignment', (e: SSEvent) => {
      try {
        const payload = JSON.parse(e.data) as AssignmentEvent
        events.value = [payload, ...events.value].slice(0, 50)
      } catch { /* malformed payload — ignore */ }
    })

    source.onerror = (e: SSEvent) => {
      // Auth errors — stop retrying
      if (e.responseCode === 401 || e.responseCode === 403) {
        triggerUnauthorized()
        source?.close()
        source = null
        return
      }
      // Adjuster changed while reconnecting — stop this loop
      if (connectedFor !== id) return

      connected.value = false
      error.value = `Connection lost. Reconnecting in ${backoff / 1000}s…`
      source?.close()
      source = null
      reconnectTimer = setTimeout(() => {
        backoff = Math.min(backoff * 2, 60_000)
        connect()
      }, backoff)
    }

    source.stream()
  }

  watch(adjusterId, (newId) => {
    if (!newId) { _close(); return }
    connect()
  }, { immediate: true })

  onUnmounted(_close)

  return { events, connected, error, disconnect: _close }
}
