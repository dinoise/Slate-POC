import { defineStore } from 'pinia'
import { ref } from 'vue'
import { incidentsApi, assignmentsApi } from '@slate/api-client'
import type { Incident, Assignment, AssignmentEvent } from '@slate/types'
import { type IncidentType, type SeverityLevel } from '@slate/types'

export const useReporterSessionStore = defineStore('reporterSession', () => {
  const incident = ref<Incident | null>(null)
  const assignment = ref<Assignment | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  async function submitIncident(payload: {
    incident_type: IncidentType
    severity: SeverityLevel
    description: string
    address: string
    latitude: number
    longitude: number
  }): Promise<Incident> {
    loading.value = true
    error.value = null
    try {
      const created = await incidentsApi.create({
        ...payload,
        external_id: crypto.randomUUID(),
        incident_datetime: new Date().toISOString(),
      })
      incident.value = created
      assignment.value = null
      // Trigger optimizer immediately so an adjuster gets assigned
      await assignmentsApi.optimize({ use_db: true })
      return created
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al enviar incidente'
      throw e
    } finally {
      loading.value = false
    }
  }

  async function loadIncident(id: number) {
    loading.value = true
    error.value = null
    try {
      incident.value = await incidentsApi.get(id)
      // Prefer the active (non-terminal) assignment; fall back to most recent overall
      const active = await assignmentsApi.byIncident(id, { active: true })
      if (active.length > 0) {
        assignment.value = active[0] ?? null
      } else {
        const all = await assignmentsApi.byIncident(id)
        assignment.value = all.sort(
          (a, b) => new Date(b.assigned_at).getTime() - new Date(a.assigned_at).getTime(),
        )[0] ?? null
      }
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar incidente'
    } finally {
      loading.value = false
    }
  }

  /** Called by TrackView when an SSE event arrives — updates local state. */
  function applySSEEvent(ev: AssignmentEvent) {
    assignment.value = {
      id: ev.assignment_id,
      incident_id: ev.incident.id,
      adjuster_id: ev.adjuster?.id ?? 0,
      status: ev.status,
      distance_km: ev.distance_km,
      travel_time_minutes: ev.travel_time_minutes,
      optimization_score: null,
      assigned_at: ev.assigned_at,
      estimated_arrival_time: null,
      actual_arrival_time: null,
      completed_at: null,
      notes: null,
      route_polyline: ev.route?.polyline ?? null,
      route_provider: ev.route?.provider ?? null,
      route_distance_m: ev.route?.distance_m ?? null,
      route_duration_s: ev.route?.duration_s ?? null,
      route_traffic_segments: ev.route?.traffic_segments ?? null,
      created_at: ev.assigned_at,
      updated_at: ev.assigned_at,
    } satisfies Assignment
  }

  async function cancelIncident() {
    if (!incident.value) return
    loading.value = true
    error.value = null
    try {
      // DELETE triggers soft_delete_incident: cancels active assignments + releases adjuster
      await incidentsApi.delete(incident.value.id)
      incident.value = null
      assignment.value = null
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cancelar'
    } finally {
      loading.value = false
    }
  }

  function reset() {
    incident.value = null
    assignment.value = null
    error.value = null
    loading.value = false
  }

  return {
    incident,
    assignment,
    loading,
    error,
    submitIncident,
    loadIncident,
    applySSEEvent,
    cancelIncident,
    reset,
  }
})
