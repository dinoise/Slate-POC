import { ref, onUnmounted, type Ref } from 'vue'
import type { AssignmentEvent } from '@slate/types'
import { getAuthToken } from '@slate/api-client'

export interface UseSSEReturn {
  events: Ref<AssignmentEvent[]>
  connected: Ref<boolean>
  error: Ref<string | null>
  disconnect: () => void
}

/**
 * Reactive SSE composable with exponential backoff reconnection.
 *
 * Connects to the notifications service stream for a given adjuster.
 * Automatically reconnects on failure with backoff (1s → 2s → 4s … max 60s).
 * The native EventSource does not support backoff — this composable
 * manages reconnection manually to avoid thundering herd on service restarts.
 */
export function useSSE(adjusterId: Ref<number | null>): UseSSEReturn {
  const events = ref<AssignmentEvent[]>([])
  const connected = ref(false)
  const error = ref<string | null>(null)

  let source: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let backoff = 1000

  const notificationsUrl =
    (import.meta as ImportMeta & { env: { VITE_NOTIFICATIONS_URL?: string } }).env
      .VITE_NOTIFICATIONS_URL ?? ''

  function connect() {
    if (!adjusterId.value) return

    // EventSource does not support custom headers — pass token as query param.
    const token = getAuthToken()
    const params = new URLSearchParams({ adjuster_id: String(adjusterId.value) })
    if (token) params.set('token', token)

    source = new EventSource(`${notificationsUrl}/notifications/stream?${params}`)

    source.addEventListener('connected', () => {
      connected.value = true
      error.value = null
      backoff = 1000
    })

    source.addEventListener('assignment', (e: MessageEvent) => {
      try {
        const payload = JSON.parse(e.data) as AssignmentEvent
        events.value = [payload, ...events.value].slice(0, 50)
      } catch {
        // malformed payload — ignore
      }
    })

    source.onerror = () => {
      connected.value = false
      source?.close()
      source = null

      error.value = `Connection lost. Reconnecting in ${backoff / 1000}s…`
      reconnectTimer = setTimeout(() => {
        backoff = Math.min(backoff * 2, 60_000)
        connect()
      }, backoff)
    }
  }

  function disconnect() {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    source?.close()
    source = null
    connected.value = false
  }

  connect()
  onUnmounted(disconnect)

  return { events, connected, error, disconnect }
}
