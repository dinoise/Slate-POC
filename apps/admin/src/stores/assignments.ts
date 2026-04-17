import { ref } from 'vue'
import { defineStore } from 'pinia'
import { assignmentsApi } from '@slate/api-client'
import type { Assignment } from '@slate/types'

export const useAssignmentsStore = defineStore('assignments', () => {
  const items = ref<Assignment[]>([])
  const selected = ref<Assignment | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  async function fetchAll(params?: Record<string, string>) {
    loading.value = true
    error.value = null
    try {
      const res = await assignmentsApi.list(params)
      type ApiResponse = Assignment[] | { items: Assignment[]; total: number }
      const list = Array.isArray(res) ? res : (res as ApiResponse & { items: Assignment[] }).items ?? []
      items.value = list
      total.value = Array.isArray(res) ? list.length : ((res as { total?: number }).total ?? list.length)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar asignaciones'
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(id: number) {
    loading.value = true
    error.value = null
    try {
      selected.value = await assignmentsApi.get(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar asignación'
    } finally {
      loading.value = false
    }
  }

  async function updateStatus(id: number, status: Assignment['status']) {
    try {
      const updated = await assignmentsApi.update(id, { status })
      const idx = items.value.findIndex((a) => a.id === id)
      if (idx !== -1) items.value[idx] = updated
      if (selected.value?.id === id) selected.value = updated
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al actualizar estado'
    }
  }

  return { items, selected, loading, error, total, fetchAll, fetchOne, updateStatus }
})
