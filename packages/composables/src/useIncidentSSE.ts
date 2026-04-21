import { ref, watch, onUnmounted, type Ref } from 'vue'
import type { AssignmentEvent } from '@slate/types'
import { getAuthToken } from '@slate/api-client'

export interface UseIncidentSSEReturn {
  event: Ref<AssignmentEvent | null>
  connected: Ref<boolean>
  error: Ref<string | null>
  disconnect: () => void
}

/**
 * SSE composable for the reporter — subscribes to assignment events for a
 * specific incident via /notifications/stream/incident?incident_id=X.
 *
 * Mirrors useSSE but keyed by incident_id instead of adjuster_id.
 * Auth token is passed as ?token= (EventSource does not support headers).
 */
export function useIncidentSSE(incidentId: Ref<number | null>): UseIncidentSSEReturn {
  const event = ref<AssignmentEvent | null>(null)
  const connected = ref(false)
  const error = ref<string | null>(null)

  let source: EventSource | null = null
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
    if (!id) {
      _close()
      return
    }

    _close()
    backoff = 1000
    connectedFor = id

    const token = getAuthToken()
    const params = new URLSearchParams({ incident_id: String(id) })
    if (token) params.set('token', token)

    source = new EventSource(`${notificationsUrl}/notifications/stream/incident?${params}`)

    source.addEventListener('connected', () => {
      connected.value = true
      error.value = null
      backoff = 1000
    })

    source.addEventListener('assignment', (e: MessageEvent) => {
      try {
        event.value = JSON.parse(e.data) as AssignmentEvent
      } catch {
        // malformed payload — ignore
      }
    })

    source.onerror = () => {
      if (connectedFor !== id) return
      connected.value = false
      source?.close()
      source = null
      error.value = `Conexión perdida. Reconectando en ${backoff / 1000}s…`
      reconnectTimer = setTimeout(() => {
        backoff = Math.min(backoff * 2, 60_000)
        connect()
      }, backoff)
    }
  }

  watch(incidentId, (newId) => {
    if (!newId) { _close(); return }
    connect()
  }, { immediate: true })

  onUnmounted(_close)

  return { event, connected, error, disconnect: _close }
}
