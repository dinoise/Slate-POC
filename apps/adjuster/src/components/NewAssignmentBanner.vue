<script setup lang="ts">
import { ref, watch } from 'vue'
import type { AssignmentEvent } from '@slate/types'

const props = defineProps<{
  event: AssignmentEvent | null
}>()

const visible = ref(false)

watch(
  () => props.event,
  (ev) => {
    if (!ev) return
    visible.value = true
    // Haptic feedback on mobile
    if ('vibrate' in navigator) {
      navigator.vibrate([200, 100, 200])
    }
  },
)

function dismiss() {
  visible.value = false
}
</script>

<template>
  <v-snackbar
    v-model="visible"
    location="top"
    color="primary"
    timeout="-1"
    multi-line
    rounded="lg"
  >
    <div class="d-flex align-center gap-2">
      <v-icon size="20">mdi-bell-ring</v-icon>
      <div>
        <div class="text-body-2 font-weight-bold">Nueva asignación</div>
        <div v-if="event?.incident_type" class="text-caption">
          {{ event.incident_type.replace(/_/g, ' ') }} · {{ event.address ?? '' }}
        </div>
      </div>
    </div>
    <template #actions>
      <v-btn variant="text" size="small" @click="dismiss">Cerrar</v-btn>
    </template>
  </v-snackbar>
</template>
