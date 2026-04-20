import { ref } from 'vue'
import { defineStore } from 'pinia'
import { adjustersApi } from '@slate/api-client'
import type { Adjuster, AdjusterCreate } from '@slate/types'

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
      type ApiResponse = Adjuster[] | { items: Adjuster[]; total: number }
      const list = Array.isArray(res) ? res : (res as ApiResponse & { items: Adjuster[] }).items ?? []
      items.value = list
      total.value = Array.isArray(res) ? list.length : ((res as { total?: number }).total ?? list.length)
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

  async function create(data: AdjusterCreate): Promise<Adjuster> {
    const adjuster = await adjustersApi.create(data)
    items.value = [adjuster, ...items.value]
    total.value += 1
    return adjuster
  }

  return { items, selected, available, loading, error, total, fetchAll, fetchOne, fetchAvailable, create }
})
