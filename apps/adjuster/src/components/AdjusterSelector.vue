<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adjustersApi } from '@slate/api-client'
import type { Adjuster } from '@slate/types'
import { useAdjusterSessionStore } from '@/stores/adjusterSession'

const store = useAdjusterSessionStore()

const adjusters = ref<Adjuster[]>([])
const selectedId = ref<number | null>(null)
const loadingList = ref(false)

onMounted(async () => {
  loadingList.value = true
  try {
    const res = await adjustersApi.list({ limit: '500' })
    adjusters.value = res.items
  } catch {
    // silently fail — list stays empty
  } finally {
    loadingList.value = false
  }
})

async function onSelect(id: number | null) {
  if (!id) return
  selectedId.value = id
  await store.selectAdjuster(id)
}

function adjusterLabel(a: Adjuster) {
  const statusEmoji = a.status === 'available' ? '🟢' : a.status === 'busy' ? '🟡' : '⚫'
  return `${statusEmoji} ${a.first_name} ${a.last_name}`
}
</script>

<template>
  <v-select
    :model-value="selectedId"
    :items="adjusters"
    :item-title="(a: Adjuster) => adjusterLabel(a)"
    :item-value="(a: Adjuster) => a.id"
    label="Seleccionar ajustador"
    density="comfortable"
    variant="outlined"
    :loading="loadingList || store.loading"
    :disabled="loadingList"
    hide-details
    @update:model-value="onSelect"
  >
    <template #prepend-inner>
      <v-icon color="primary">mdi-account-hard-hat</v-icon>
    </template>
  </v-select>
</template>
