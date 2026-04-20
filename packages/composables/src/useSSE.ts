import { ref, watch, onUnmounted, type Ref } from 'vue'
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
 * Watches `adjusterId` — when it changes, the old connection is closed and a
 * new one is opened for the new adjuster. If `adjusterId` becomes null the
 * stream is disconnected until a new value arrives.
 *
 * The native EventSource does not support custom headers — the auth token is
 * passed as a `?token=` query parameter (handled by the notifications service).
 */
export function useSSE(adjusterId: Ref<number | null>): UseSSEReturn {
  const events = ref<AssignmentEvent[]>([])
  const connected = ref(false)
  const error = ref<string | null>(null)

  let source: EventSource | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let backoff = 1000
  // Track which adjuster the open connection belongs to so reconnect logic
  // doesn't re-open a stale connection after the adjuster has been swapped out.
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
    const id = adjusterId.value
    if (!id) {
      _close()
      return
    }

    _close()
    backoff = 1000
    connectedFor = id

    const token = getAuthToken()
    const params = new URLSearchParams({ adjuster_id: String(id) })
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
      // If the adjuster changed while we were waiting for this error, don't
      // schedule a reconnect for the old adjuster.
      if (connectedFor !== id) return

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

  // React to adjuster changes (including null → id and id → different id).
  watch(adjusterId, (newId) => {
    if (!newId) {
      _close()
      return
    }
    connect()
  }, { immediate: true })

  onUnmounted(_close)

  return { events, connected, error, disconnect: _close }
}
