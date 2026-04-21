import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adjustersApi, assignmentsApi } from '@slate/api-client'
import type { Adjuster, Assignment } from '@slate/types'
import { AdjusterStatus, ACTIVE_ASSIGNMENT_STATUSES, TERMINAL_ASSIGNMENT_STATUSES } from '@slate/types'

export const useAdjusterSessionStore = defineStore('adjusterSession', () => {
  const adjuster = ref<Adjuster | null>(null)
  const activeAssignment = ref<Assignment | null>(null)
  const sseConnected = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)

  const adjusterId = computed(() => adjuster.value?.id ?? null)

  async function selectAdjuster(id: number) {
    loading.value = true
    error.value = null
    adjuster.value = null
    activeAssignment.value = null

    try {
      adjuster.value = await adjustersApi.get(id)
      await loadActiveAssignment(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar ajustador'
    } finally {
      loading.value = false
    }
  }

  async function loadActiveAssignment(id: number) {
    try {
      const assignments = await assignmentsApi.byAdjuster(id)
      const active = assignments.find((a) => ACTIVE_ASSIGNMENT_STATUSES.has(a.status))
      activeAssignment.value = active ?? null
    } catch {
      // No active assignment — silently ignore
      activeAssignment.value = null
    }
  }

  async function updateAssignmentStatus(
    assignmentId: number,
    status: Assignment['status'],
  ) {
    const updated = await assignmentsApi.updateStatus(assignmentId, status)
    activeAssignment.value = updated

    if (TERMINAL_ASSIGNMENT_STATUSES.has(status)) {
      // Mark adjuster available again before clearing UI
      if (adjuster.value) {
        try {
          await adjustersApi.update(adjuster.value.id, { status: AdjusterStatus.AVAILABLE })
          adjuster.value = { ...adjuster.value, status: AdjusterStatus.AVAILABLE }
        } catch {
          // Non-fatal — UI still clears
        }
      }
      activeAssignment.value = null
    }
  }

  function setActiveAssignmentFromSSE(assignment: Assignment) {
    activeAssignment.value = assignment
  }

  function clear() {
    adjuster.value = null
    activeAssignment.value = null
    sseConnected.value = false
    error.value = null
  }

  return {
    adjuster,
    activeAssignment,
    sseConnected,
    loading,
    error,
    adjusterId,
    selectAdjuster,
    loadActiveAssignment,
    updateAssignmentStatus,
    setActiveAssignmentFromSSE,
    clear,
  }
})
