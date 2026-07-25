<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import type { AgentMessage, AgentCardType } from '@slate/types'

const props = defineProps<{
  message: AgentMessage
}>()

const emit = defineEmits<{
  dismiss: [id: string]
}>()

const md = new MarkdownIt({ breaks: true, linkify: false, html: false })

const renderedContent = computed(() =>
  DOMPurify.sanitize(md.render(props.message.content)),
)

const config: Record<AgentCardType, { icon: string; color: string; title: string }> = {
  briefing:          { icon: 'mdi-clipboard-text',       color: 'primary',  title: 'Briefing del siniestro' },
  procedures:        { icon: 'mdi-format-list-checks',   color: 'secondary', title: 'Procedimientos' },
  alert:             { icon: 'mdi-alert',                color: 'error',    title: 'Alerta' },
  note_logged:       { icon: 'mdi-note-check',           color: 'success',  title: 'Nota registrada' },
  service_requested: { icon: 'mdi-truck-fast',           color: 'warning',  title: 'Servicio solicitado' },
  chat:              { icon: 'mdi-robot-outline',        color: 'surface',  title: 'Asistente' },
}

const cardConfig = computed(() => config[props.message.cardType] ?? config.chat)

const formattedTime = computed(() => {
  const d = new Date(props.message.timestamp)
  return d.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit' })
})
</script>

<template>
  <v-card
    class="agent-card mb-2"
    :class="[`agent-card--${message.cardType}`, { 'agent-card--historical': message.isHistorical }]"
    rounded="lg"
    elevation="1"
  >
    <!-- Header -->
    <v-card-item class="py-2 px-3">
      <template #prepend>
        <v-icon
          :icon="cardConfig.icon"
          :color="cardConfig.color === 'surface' ? 'grey-darken-1' : cardConfig.color"
          size="20"
        />
      </template>
      <v-card-title class="text-body-2 font-weight-medium">
        {{ message.role === 'user' ? 'Tú' : cardConfig.title }}
      </v-card-title>
      <template #append>
        <div class="d-flex align-center gap-1">
          <span class="text-caption text-medium-emphasis">{{ formattedTime }}</span>
          <v-chip v-if="message.isHistorical" size="x-small" color="grey" variant="tonal">
            prev.
          </v-chip>
          <v-btn
            v-if="message.cardType === 'alert'"
            icon="mdi-close"
            size="x-small"
            variant="text"
            @click="emit('dismiss', message.id)"
          />
        </div>
      </template>
    </v-card-item>

    <v-divider />

    <!-- Content -->
    <v-card-text class="pa-3">
      <!-- User message — plain text -->
      <template v-if="message.role === 'user'">
        <p class="text-body-2 mb-0">{{ message.content }}</p>
      </template>

      <!-- Agent response — rendered markdown -->
      <template v-else>
        <!-- Streaming placeholder -->
        <template v-if="!message.content">
          <div class="d-flex align-center gap-2">
            <v-progress-circular size="14" width="2" indeterminate color="grey" />
            <span class="text-body-2 text-medium-emphasis">Analizando...</span>
          </div>
        </template>

        <template v-else>
          <!-- Alert variant: prominent display -->
          <v-alert
            v-if="message.cardType === 'alert'"
            type="error"
            variant="tonal"
            density="compact"
            class="mb-0"
          >
            <!-- eslint-disable-next-line vue/no-v-html -->
            <div class="agent-prose" v-html="renderedContent" />
          </v-alert>

          <!-- All other variants: standard prose -->
          <!-- eslint-disable-next-line vue/no-v-html -->
          <div v-else class="agent-prose text-body-2" v-html="renderedContent" />
        </template>
      </template>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.agent-card {
  contain: layout;
}

.agent-card--historical {
  opacity: 0.75;
}

.agent-card--alert {
  border-left: 3px solid rgb(var(--v-theme-error));
}

.agent-prose {
  overflow-wrap: break-word;
  word-break: break-word;
}

.agent-prose :deep(p) {
  margin-bottom: 0.4rem;
}

.agent-prose :deep(p:last-child) {
  margin-bottom: 0;
}

.agent-prose :deep(ul),
.agent-prose :deep(ol) {
  padding-left: 1.2rem;
  margin-bottom: 0.4rem;
}

.agent-prose :deep(li) {
  margin-bottom: 0.2rem;
}

.agent-prose :deep(strong) {
  font-weight: 600;
}

.agent-prose :deep(code) {
  font-size: 0.85em;
  background: rgba(0, 0, 0, 0.06);
  padding: 0.1em 0.3em;
  border-radius: 3px;
}
</style>
