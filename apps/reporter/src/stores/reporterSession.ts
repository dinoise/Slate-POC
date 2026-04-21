import { defineStore } from 'pinia'
import { ref } from 'vue'
import { incidentsApi, assignmentsApi } from '@slate/api-client'
import type { Incident, Assignment } from '@slate/types'
import { type IncidentType, type SeverityLevel, ACTIVE_ASSIGNMENT_STATUSES, TERMINAL_ASSIGNMENT_STATUSES } from '@slate/types'

export const useReporterSessionStore = defineStore('reporterSession', () => {
  const incident = ref<Incident | null>(null)
  const assignment = ref<Assignment | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  // Stored as a ref so HMR module re-evaluation doesn't orphan the interval ID
  const _pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

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
      // Trigger optimizer immediately
      await assignmentsApi.optimize({ use_db: true })
      // Start polling for assignment
      startPolling(created.id)
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
      await pollAssignment(id)
      // Only poll if no terminal assignment already found
      const alreadyDone = assignment.value && TERMINAL_ASSIGNMENT_STATUSES.has(assignment.value.status)
      if (!alreadyDone) startPolling(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar incidente'
    } finally {
      loading.value = false
    }
  }

  async function pollAssignment(incidentId: number) {
    try {
      // Refresh incident status in parallel with assignment list
      const [list, freshIncident] = await Promise.all([
        assignmentsApi.byIncident(incidentId),
        incidentsApi.get(incidentId),
      ])
      incident.value = freshIncident

      // Pick the most recent assignment so reporter tracks the full flow
      const latest = list.sort(
        (a, b) => new Date(b.assigned_at).getTime() - new Date(a.assigned_at).getTime(),
      )[0]
      if (latest) {
        assignment.value = latest
        // Stop polling only when terminal — keep updating while active
        if (TERMINAL_ASSIGNMENT_STATUSES.has(latest.status)) stopPolling()
      } else if (!ACTIVE_ASSIGNMENT_STATUSES.has(assignment.value?.status ?? 'assigned')) {
        assignment.value = null
      }
    } catch {
      // silent — keep polling
    }
  }

  function startPolling(incidentId: number) {
    stopPolling()
    _pollTimer.value = setInterval(() => pollAssignment(incidentId), 3_000)
  }

  function stopPolling() {
    if (_pollTimer.value !== null) {
      clearInterval(_pollTimer.value)
      _pollTimer.value = null
    }
  }

  async function cancelIncident() {
    if (!incident.value) return
    loading.value = true
    error.value = null
    try {
      await incidentsApi.delete(incident.value.id)
      stopPolling()
      incident.value = null
      assignment.value = null
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cancelar'
    } finally {
      loading.value = false
    }
  }

  function reset() {
    stopPolling()
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
    pollAssignment,
    startPolling,
    stopPolling,
    cancelIncident,
    reset,
  }
})
