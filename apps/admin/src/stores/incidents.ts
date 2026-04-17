import { ref } from 'vue'
import { defineStore } from 'pinia'
import { incidentsApi } from '@slate/api-client'
import type { Incident } from '@slate/types'

export const useIncidentsStore = defineStore('incidents', () => {
  const items = ref<Incident[]>([])
  const selected = ref<Incident | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  async function fetchAll(params?: Record<string, string>) {
    loading.value = true
    error.value = null
    try {
      const res = await incidentsApi.list(params)
      items.value = res.items
      total.value = res.total
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar incidentes'
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(id: number) {
    loading.value = true
    error.value = null
    try {
      selected.value = await incidentsApi.get(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar incidente'
    } finally {
      loading.value = false
    }
  }

  return { items, selected, loading, error, total, fetchAll, fetchOne }
})
