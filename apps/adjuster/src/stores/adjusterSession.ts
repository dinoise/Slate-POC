import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { adjustersApi, assignmentsApi } from '@slate/api-client'
import type { Adjuster, Assignment } from '@slate/types'

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
    const ACTIVE = new Set(['assigned', 'accepted', 'en_route', 'arrived', 'in_progress'])
    try {
      const assignments = await assignmentsApi.byAdjuster(id)
      const active = assignments.find((a) => ACTIVE.has(a.status))
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
    // If terminal status, clear active assignment
    if (status === 'completed' || status === 'cancelled') {
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
