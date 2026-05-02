<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  isStreaming: boolean
  isLoading: boolean
  hasSession: boolean
  unreadCount: number
}>()

const statusIcon = computed(() => {
  if (props.isLoading || props.isStreaming) return 'mdi-robot-outline'
  if (!props.hasSession) return 'mdi-robot-off-outline'
  return 'mdi-robot-outline'
})

const statusColor = computed(() => {
  if (!props.hasSession) return 'grey'
  if (props.isLoading || props.isStreaming) return 'warning'
  return 'success'
})

const statusText = computed(() => {
  if (props.isLoading) return 'Iniciando asistente...'
  if (props.isStreaming) return 'Analizando...'
  if (!props.hasSession) return 'Asistente inactivo'
  return 'Asistente listo'
})
</script>

<template>
  <div class="agent-status-bar d-flex align-center px-3 py-2 gap-2">
    <v-progress-circular
      v-if="isLoading || isStreaming"
      size="18"
      width="2"
      indeterminate
      :color="statusColor"
    />
    <v-icon v-else :icon="statusIcon" :color="statusColor" size="20" />

    <span class="text-body-2 font-weight-medium flex-grow-1">{{ statusText }}</span>

    <v-badge
      v-if="unreadCount > 0"
      :content="unreadCount"
      color="error"
      inline
    >
      <v-icon icon="mdi-bell" size="18" color="grey-darken-1" />
    </v-badge>

    <span class="text-caption text-medium-emphasis">Field Guide</span>
  </div>
</template>

<style scoped>
.agent-status-bar {
  min-height: 48px;
}
</style>
