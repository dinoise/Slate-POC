<script setup lang="ts">
import type { AgentMessage } from '@slate/types'
import AgentCard from './AgentCard.vue'

defineProps<{
  messages: AgentMessage[]
}>()

const emit = defineEmits<{
  dismiss: [id: string]
}>()
</script>

<template>
  <div class="agent-feed pa-3">
    <template v-if="messages.length === 0">
      <div class="d-flex flex-column align-center justify-center py-8 text-medium-emphasis">
        <v-icon icon="mdi-robot-outline" size="40" class="mb-2" />
        <span class="text-body-2">El asistente está listo</span>
        <span class="text-caption">Las actualizaciones aparecerán aquí</span>
      </div>
    </template>

    <template v-else>
      <!-- Newest messages at the bottom — natural chat order -->
      <AgentCard
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
        @dismiss="emit('dismiss', $event)"
      />
    </template>
  </div>
</template>

<style scoped>
.agent-feed {
  overflow-y: auto;
  flex: 1;
}
</style>
