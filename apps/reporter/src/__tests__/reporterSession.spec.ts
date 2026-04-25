import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useReporterSessionStore } from '../stores/reporterSession'
import type { Assignment, AssignmentEvent, Incident } from '@slate/types'

// ── Mocks ─────────────────────────────────────────────────────────────────────

vi.mock('@slate/api-client', () => ({
  incidentsApi: {
    get: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  assignmentsApi: {
    byIncident: vi.fn(),
    optimize: vi.fn(),
  },
}))

import { incidentsApi, assignmentsApi } from '@slate/api-client'

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeIncident(overrides: Partial<Incident> = {}): Incident {
  return {
    id: 1, incident_type: 'collision', severity: 3, status: 'assigned',
    address: 'Calle 1', latitude: 19.4, longitude: -99.1,
    description: null, external_id: 'ext-1', reported_by_user_id: null,
    incident_datetime: '2026-01-01T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

function makeAssignment(overrides: Partial<Assignment> = {}): Assignment {
  return {
    id: 1, incident_id: 1, adjuster_id: 10, status: 'assigned',
    assigned_at: '2026-01-01T00:00:00Z', distance_km: 2.5,
    travel_time_minutes: 10, optimization_score: null,
    estimated_arrival_time: null, actual_arrival_time: null, completed_at: null,
    notes: null, route_polyline: null, route_provider: null,
    route_distance_m: null, route_duration_s: null, route_traffic_segments: null,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  }
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('reporterSession store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  // ── loadIncident ────────────────────────────────────────────────────────────

  describe('loadIncident', () => {
    it('sets assignment to the active one when mixed with cancelled', async () => {
      const store = useReporterSessionStore()
      const incident = makeIncident()
      const cancelled = makeAssignment({ id: 2, status: 'cancelled', assigned_at: '2026-01-01T01:00:00Z' })
      const active = makeAssignment({ id: 1, status: 'assigned', assigned_at: '2026-01-01T00:00:00Z' })

      vi.mocked(incidentsApi.get).mockResolvedValue(incident)
      // cancelled has a later assigned_at — naive sort would pick it
      vi.mocked(assignmentsApi.byIncident).mockResolvedValue([cancelled, active])

      await store.loadIncident(1)

      expect(store.assignment?.status).toBe('assigned')
      expect(store.assignment?.id).toBe(1)
    })

    it('falls back to most recent when all assignments are terminal', async () => {
      const store = useReporterSessionStore()
      const incident = makeIncident({ status: 'completed' })
      const older = makeAssignment({ id: 1, status: 'cancelled', assigned_at: '2026-01-01T00:00:00Z' })
      const newer = makeAssignment({ id: 2, status: 'completed', assigned_at: '2026-01-01T02:00:00Z' })

      vi.mocked(incidentsApi.get).mockResolvedValue(incident)
      vi.mocked(assignmentsApi.byIncident).mockResolvedValue([older, newer])

      await store.loadIncident(1)

      expect(store.assignment?.id).toBe(2)
    })

    it('sets assignment to null when no assignments exist', async () => {
      const store = useReporterSessionStore()
      vi.mocked(incidentsApi.get).mockResolvedValue(makeIncident({ status: 'pending' }))
      vi.mocked(assignmentsApi.byIncident).mockResolvedValue([])

      await store.loadIncident(1)

      expect(store.assignment).toBeNull()
    })

    it('sets error and keeps assignment null on API failure', async () => {
      const store = useReporterSessionStore()
      vi.mocked(incidentsApi.get).mockRejectedValue(new Error('Network error'))

      await store.loadIncident(1)

      expect(store.error).toBe('Network error')
      expect(store.assignment).toBeNull()
      expect(store.loading).toBe(false)
    })
  })

  // ── applySSEEvent ───────────────────────────────────────────────────────────

  describe('applySSEEvent', () => {
    it('updates assignment from SSE payload', () => {
      const store = useReporterSessionStore()
      const ev: AssignmentEvent = {
        assignment_id: 5,
        status: 'accepted', event_type: 'assignment.updated',
        distance_km: 3.1, travel_time_minutes: 12,
        assigned_at: '2026-01-01T00:00:00Z',
        incident: {
          id: 1, type: 'collision', severity: 3,
          description: null, address: 'Calle 1', latitude: 19.4, longitude: -99.1,
        },
        adjuster: { id: 10, latitude: 19.3, longitude: -99.2 },
        route: null,
      }

      store.applySSEEvent(ev)

      expect(store.assignment?.id).toBe(5)
      expect(store.assignment?.status).toBe('accepted')
      expect(store.assignment?.adjuster_id).toBe(10)
    })
  })

  // ── cancelIncident ──────────────────────────────────────────────────────────

  describe('cancelIncident', () => {
    it('clears incident and assignment on success', async () => {
      const store = useReporterSessionStore()
      store.incident = makeIncident()
      store.assignment = makeAssignment()
      vi.mocked(incidentsApi.delete).mockResolvedValue(undefined)

      await store.cancelIncident()

      expect(store.incident).toBeNull()
      expect(store.assignment).toBeNull()
      expect(store.loading).toBe(false)
    })

    it('does nothing when no incident is set', async () => {
      const store = useReporterSessionStore()
      await store.cancelIncident()
      expect(incidentsApi.delete).not.toHaveBeenCalled()
    })
  })
})
