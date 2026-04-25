import { ref, computed, onMounted, onUnmounted } from 'vue'
import type { AssignmentEvent } from '@slate/types'
import { ACTIVE_ASSIGNMENT_STATUSES } from '@slate/types'
import { getAuthToken, notificationsApi } from '@slate/api-client'

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
 * Unlike `useSSE` (which holds a rolling array of events for one adjuster),
 * this composable maintains a `Map<assignment_id, AssignmentEvent>` so each
 * new event replaces the previous state of the same assignment — the map
 * always reflects the current state of every known assignment.
 *
 * Startup pattern — Snapshot REST + Delta SSE:
 *   1. Open EventSource first — events are queued in memory.
 *   2. Fetch GET /notifications/snapshot/observatory (atomic bulk state).
 *   3. After snapshot resolves, populate the map from snapshot, then replay
 *      queued events with assigned_at >= snapshot fetch start time (newer
 *      events win over snapshot; older events already covered by snapshot
 *      are discarded).
 *
 * Reconnects automatically with exponential backoff (1s → 60s max).
 */
export function useObservatorySSE() {
  const assignments = ref<Map<number, AssignmentEvent>>(new Map())
  const connected = ref(false)
  const lastEventAt = ref<string | null>(null)
  const error = ref<string | null>(null)

  let source: EventSource | null = null
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
    // App.vue's onMounted has called initialize() (Vue mounts children before
    // parents). Fall back to sessionStorage directly — same source of truth.
    return getAuthToken() ?? sessionStorage.getItem('gid_token')
  }

  function _openSSE() {
    const token = _getToken()
    const params = new URLSearchParams()
    if (token) params.set('token', token)
    const qs = params.toString() ? `?${params}` : ''

    source = new EventSource(`${notificationsUrl}/notifications/stream/observatory${qs}`)

    source.addEventListener('connected', () => {
      connected.value = true
      error.value = null
      backoff = 1000
    })

    source.addEventListener('assignment', (e: MessageEvent) => {
      try {
        const event = JSON.parse(e.data) as AssignmentEvent
        lastEventAt.value = new Date().toISOString()

        if (!_snapshotLoaded) {
          // Snapshot still in flight — queue the event for later replay
          _eventQueue.push(event)
        } else {
          // Snapshot already applied — update map directly
          assignments.value = new Map(assignments.value).set(event.assignment_id, event)
        }
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

  async function _loadSnapshot() {
    try {
      const snapshot = await notificationsApi.observatorySnapshot()
      const map = new Map<number, AssignmentEvent>()

      // Populate from snapshot — atomic state captured in DB at fetch time
      for (const ev of snapshot) {
        map.set(ev.assignment_id, ev)
      }

      // Replay queued SSE events: only apply those with assigned_at newer
      // than when the snapshot fetch started — events already covered by
      // the snapshot are discarded (snapshot is authoritative for them).
      for (const ev of _eventQueue) {
        if (!ev.assigned_at || ev.assigned_at >= _snapshotStartedAt) {
          map.set(ev.assignment_id, ev)
        }
      }

      assignments.value = map
    } catch {
      // Snapshot failed — accept whatever arrived via SSE during the attempt
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

    // Reset snapshot state for this connection attempt
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
