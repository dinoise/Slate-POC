import { ref, computed, onMounted, onUnmounted } from 'vue'
import { SSE, type SSEvent } from 'sse.js'
import type { AssignmentEvent } from '@slate/types'
import { ACTIVE_ASSIGNMENT_STATUSES } from '@slate/types'
import { getAuthToken, triggerUnauthorized, notificationsApi } from '@slate/api-client'

export interface UseObservatorySSEReturn {
  /** All known assignments keyed by id — updated in place on each event. */
  assignments: ReturnType<typeof ref<Map<number, AssignmentEvent>>>
  /** Subset of assignments whose status is considered "active". */
  activeAssignments: ReturnType<typeof computed<AssignmentEvent[]>>
  connected: ReturnType<typeof ref<boolean>>
  /** ISO timestamp of the last received event, for freshness indicator. */
  lastEventAt: ReturnType<typeof ref<string | null>>
  error: ReturnType<typeof ref<string | null>>
  disconnect: () => void
}

/**
 * Global SSE composable for the admin observatory.
 *
 * Connects to `/notifications/stream/observatory` — a channel that receives
 * every assignment event regardless of adjuster or incident.
 *
 * Uses sse.js instead of native EventSource so that:
 * - The auth token is sent as `Authorization: Bearer` header
 * - 401/403 in SSE or snapshot triggers triggerUnauthorized() and redirects to login
 * - Works cross-browser (Firefox + Chromium) — sse.js uses XHR internally
 * - Network drops reconnect with exponential backoff (1s → 60s)
 *
 * Startup pattern — Snapshot REST + Delta SSE:
 *   1. Open SSE first — events are queued in memory while snapshot loads.
 *   2. Fetch GET /notifications/snapshot/observatory (atomic bulk state).
 *   3. After snapshot resolves, populate the map from snapshot, then replay
 *      queued events with assigned_at >= snapshot fetch start time (newer
 *      events win over snapshot; older events already covered by snapshot
 *      are discarded).
 */
export function useObservatorySSE() {
  const assignments = ref<Map<number, AssignmentEvent>>(new Map())
  const connected = ref(false)
  const lastEventAt = ref<string | null>(null)
  const error = ref<string | null>(null)

  let source: SSE | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let backoff = 1000

  // Snapshot load state — reset on each connect() call
  let _snapshotLoaded = false
  let _eventQueue: AssignmentEvent[] = []
  let _snapshotStartedAt = ''

  const notificationsUrl =
    (import.meta as ImportMeta & { env: { VITE_NOTIFICATIONS_URL?: string } }).env
      .VITE_NOTIFICATIONS_URL ?? ''

  const activeAssignments = computed<AssignmentEvent[]>(() =>
    [...assignments.value.values()].filter((e) =>
      ACTIVE_ASSIGNMENT_STATUSES.has(e.status),
    ),
  )

  function _close() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    source?.close()
    source = null
    connected.value = false
  }

  function _getToken(): string | null {
    // getAuthToken() may be null if onMounted of this composable runs before
    // App.vue's onMounted has called initialize(). Fall back to sessionStorage.
    return getAuthToken() ?? sessionStorage.getItem('gid_token')
  }

  function _openSSE() {
    const token = _getToken()
    const headers: Record<string, string> = {}
    if (token) headers['Authorization'] = `Bearer ${token}`

    source = new SSE(`${notificationsUrl}/notifications/stream/observatory`, {
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
        const ev = JSON.parse(e.data) as AssignmentEvent
        lastEventAt.value = new Date().toISOString()

        if (!_snapshotLoaded) {
          // Snapshot still in flight — queue for later replay
          _eventQueue.push(ev)
        } else {
          assignments.value = new Map(assignments.value).set(ev.assignment_id, ev)
        }
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

  async function _loadSnapshot() {
    try {
      const snapshot = await notificationsApi.observatorySnapshot()
      const map = new Map<number, AssignmentEvent>()

      for (const ev of snapshot) {
        map.set(ev.assignment_id, ev)
      }

      // Replay queued SSE events newer than when the snapshot fetch started
      for (const ev of _eventQueue) {
        if (!ev.assigned_at || ev.assigned_at >= _snapshotStartedAt) {
          map.set(ev.assignment_id, ev)
        }
      }

      assignments.value = map
    } catch (err: unknown) {
      // Detect 401 from snapshot fetch
      if (err instanceof Error && err.message.includes('401')) {
        triggerUnauthorized()
        return
      }
      // Other errors — accept whatever arrived via SSE during the attempt
      const map = new Map(assignments.value)
      for (const ev of _eventQueue) {
        map.set(ev.assignment_id, ev)
      }
      assignments.value = map
    } finally {
      _snapshotLoaded = true
      _eventQueue = []
    }
  }

  async function connect() {
    _close()
    backoff = 1000

    _snapshotLoaded = false
    _eventQueue = []
    _snapshotStartedAt = new Date().toISOString()

    // Open SSE first — events are queued while snapshot loads
    _openSSE()

    // Fetch snapshot in parallel; resolves the queue after
    await _loadSnapshot()
  }

  onMounted(connect)
  onUnmounted(_close)

  return { assignments, activeAssignments, connected, lastEventAt, error, disconnect: _close }
}
