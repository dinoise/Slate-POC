import { ref } from 'vue'
import { defineStore } from 'pinia'
import { adjustersApi } from '@slate/api-client'
import type { Adjuster } from '@slate/types'

export const useAdjustersStore = defineStore('adjusters', () => {
  const items = ref<Adjuster[]>([])
  const selected = ref<Adjuster | null>(null)
  const available = ref<Adjuster[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const total = ref(0)

  async function fetchAll(params?: Record<string, string>) {
    loading.value = true
    error.value = null
    try {
      const res = await adjustersApi.list(params)
      items.value = res.items
      total.value = res.total
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar ajustadores'
    } finally {
      loading.value = false
    }
  }

  async function fetchOne(id: number) {
    loading.value = true
    error.value = null
    try {
      selected.value = await adjustersApi.get(id)
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar ajustador'
    } finally {
      loading.value = false
    }
  }

  async function fetchAvailable() {
    try {
      available.value = await adjustersApi.available()
    } catch (e) {
      error.value = e instanceof Error ? e.message : 'Error al cargar disponibles'
    }
  }

  return { items, selected, available, loading, error, total, fetchAll, fetchOne, fetchAvailable }
})
