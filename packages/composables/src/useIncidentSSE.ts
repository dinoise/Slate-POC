import { ref, watch, onUnmounted, type Ref } from 'vue'
import { SSE, type SSEvent } from 'sse.js'
import type { AssignmentEvent } from '@slate/types'
import { getAuthToken, triggerUnauthorized } from '@slate/api-client'

export interface UseIncidentSSEReturn {
  event: Ref<AssignmentEvent | null>
  connected: Ref<boolean>
  error: Ref<string | null>
  disconnect: () => void
}

/**
 * SSE composable for the reporter — subscribes to assignment events for a
 * specific incident via /notifications/stream/incidents/{id}.
 *
 * Uses sse.js instead of native EventSource so that:
 * - The auth token is sent as `Authorization: Bearer` header
 * - 401/403 triggers triggerUnauthorized() and stops reconnecting
 * - Works cross-browser (Firefox + Chromium) — sse.js uses XHR internally
 * - Network drops reconnect with exponential backoff (1s → 60s)
 */
export function useIncidentSSE(incidentId: Ref<number | null>): UseIncidentSSEReturn {
  const event = ref<AssignmentEvent | null>(null)
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
  }

  function connect() {
    const id = incidentId.value
    if (!id) { _close(); return }

    _close()
    backoff = 1000
    connectedFor = id

    const token = getAuthToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`

    source = new SSE(`${notificationsUrl}/notifications/stream/incidents/${id}`, {
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
        event.value = JSON.parse(e.data) as AssignmentEvent
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
      // Incident changed while reconnecting — stop this loop
      if (connectedFor !== id) return

      connected.value = false
      error.value = `Conexión perdida. Reconectando en ${backoff / 1000}s…`
      source?.close()
      source = null
      reconnectTimer = setTimeout(() => {
        backoff = Math.min(backoff * 2, 60_000)
        connect()
      }, backoff)
    }

    source.stream()
  }

  watch(incidentId, (newId) => {
    if (!newId) { _close(); return }
    connect()
  }, { immediate: true })

  onUnmounted(_close)

  return { event, connected, error, disconnect: _close }
}
