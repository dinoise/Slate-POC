<script setup lang="ts">
import { computed } from 'vue'
import type { Assignment } from '@slate/types'
import { AssignmentStatus } from '@slate/types'
import { useAdjusterSessionStore } from '@/stores/adjusterSession'

const props = defineProps<{
  assignment: Assignment
  incidentLat?: number | null
  incidentLon?: number | null
  incidentType?: string | null
  incidentAddress?: string | null
  severity?: number | null
}>()

const emit = defineEmits<{
  statusUpdated: [status: Assignment['status']]
}>()

const store = useAdjusterSessionStore()
const updating = computed(() => store.loading)

const STATUS_FLOW: Record<string, { next: Assignment['status']; label: string; color: string; icon: string } | null> = {
  [AssignmentStatus.ASSIGNED]:    { next: AssignmentStatus.ACCEPTED,    label: 'Aceptar asignación', color: 'success', icon: 'mdi-check-circle' },
  [AssignmentStatus.ACCEPTED]:    { next: AssignmentStatus.EN_ROUTE,    label: 'Iniciar ruta',       color: 'primary', icon: 'mdi-car-arrow-right' },
  [AssignmentStatus.EN_ROUTE]:    { next: AssignmentStatus.ARRIVED,     label: 'He llegado',         color: 'warning', icon: 'mdi-map-marker-check' },
  [AssignmentStatus.ARRIVED]:     { next: AssignmentStatus.IN_PROGRESS, label: 'Iniciar atención',   color: 'purple',  icon: 'mdi-tools' },
  [AssignmentStatus.IN_PROGRESS]: { next: AssignmentStatus.COMPLETED,   label: 'Completar atención', color: 'info',    icon: 'mdi-clipboard-check' },
  [AssignmentStatus.COMPLETED]:   null,
  [AssignmentStatus.CANCELLED]:   null,
}

const STATUS_LABELS: Record<string, string> = {
  [AssignmentStatus.ASSIGNED]:    'Asignada',
  [AssignmentStatus.ACCEPTED]:    'Aceptada',
  [AssignmentStatus.EN_ROUTE]:    'En camino',
  [AssignmentStatus.ARRIVED]:     'En sitio',
  [AssignmentStatus.IN_PROGRESS]: 'En atención',
  [AssignmentStatus.COMPLETED]:   'Completada',
  [AssignmentStatus.CANCELLED]:   'Cancelada',
}

const STATUS_COLORS: Record<string, string> = {
  [AssignmentStatus.ASSIGNED]:    'indigo',
  [AssignmentStatus.ACCEPTED]:    'primary',
  [AssignmentStatus.EN_ROUTE]:    'blue',
  [AssignmentStatus.ARRIVED]:     'purple',
  [AssignmentStatus.IN_PROGRESS]: 'deep-purple',
  [AssignmentStatus.COMPLETED]:   'success',
  [AssignmentStatus.CANCELLED]:   'error',
}

const nextAction = computed(() => STATUS_FLOW[props.assignment.status] ?? null)
const statusLabel = computed(() => STATUS_LABELS[props.assignment.status] ?? props.assignment.status)
const statusColor = computed(() => STATUS_COLORS[props.assignment.status] ?? 'grey')

const mapsUrl = computed(() => {
  if (!props.incidentLat || !props.incidentLon) return null
  return `https://maps.google.com/?q=${props.incidentLat},${props.incidentLon}`
})

const severityColor = computed(() => {
  const s = props.severity ?? 0
  if (s >= 4) return 'error'
  if (s >= 3) return 'warning'
  if (s >= 2) return 'info'
  return 'success'
})

async function advance() {
  const action = nextAction.value
  if (!action) return
  await store.updateAssignmentStatus(props.assignment.id, action.next)
  emit('statusUpdated', action.next)
}

async function cancel() {
  await store.updateAssignmentStatus(props.assignment.id, 'cancelled')
  emit('statusUpdated', 'cancelled')
}
</script>

<template>
  <v-card color="surface" rounded="lg" class="assignment-card">
    <v-card-title class="d-flex align-center gap-2 pb-1">
      <v-icon color="error" size="20">mdi-alert-circle</v-icon>
      <span class="text-body-1 font-weight-bold text-truncate">
        {{ incidentType?.replace(/_/g, ' ') ?? 'Siniestro' }}
      </span>
      <v-spacer />
      <v-chip :color="statusColor" size="x-small" label>{{ statusLabel }}</v-chip>
    </v-card-title>

    <v-card-text class="pt-1 pb-2">
      <!-- Severity -->
      <div v-if="severity" class="d-flex align-center gap-1 mb-2">
        <v-icon :color="severityColor" size="14">mdi-circle</v-icon>
        <span class="text-caption text-medium-emphasis">Severidad {{ severity }}/5</span>
      </div>

      <!-- Address -->
      <div v-if="incidentAddress" class="d-flex align-start gap-1 mb-2">
        <v-icon color="primary" size="16" class="mt-0-5">mdi-map-marker</v-icon>
        <span class="text-body-2">{{ incidentAddress }}</span>
      </div>

      <!-- Distance / ETA — prefer precise route data when available -->
      <div class="d-flex gap-3 mb-3">
        <div
          v-if="assignment.route_distance_m ?? assignment.distance_km"
          class="text-caption text-medium-emphasis"
        >
          <v-icon size="14">mdi-road-variant</v-icon>
          <template v-if="assignment.route_distance_m">
            {{ (assignment.route_distance_m / 1000).toFixed(1) }} km
          </template>
          <template v-else>
            {{ assignment.distance_km?.toFixed(1) }} km
          </template>
        </div>
        <div
          v-if="assignment.route_duration_s ?? assignment.travel_time_minutes"
          class="text-caption text-medium-emphasis"
        >
          <v-icon size="14">mdi-clock-outline</v-icon>
          <template v-if="assignment.route_duration_s">
            {{ Math.round(assignment.route_duration_s / 60) }} min
          </template>
          <template v-else>
            {{ assignment.travel_time_minutes }} min
          </template>
        </div>
      </div>

      <!-- Primary action button -->
      <v-btn
        v-if="nextAction"
        :color="nextAction.color"
        :prepend-icon="nextAction.icon"
        :loading="updating"
        block
        size="large"
        class="mb-2"
        @click="advance"
      >
        {{ nextAction.label }}
      </v-btn>

      <!-- Completed state -->
      <v-alert
        v-else-if="assignment.status === AssignmentStatus.COMPLETED"
        type="success"
        density="compact"
        class="mb-2"
      >
        Atención completada
      </v-alert>

      <!-- Open in Maps -->
      <v-btn
        v-if="mapsUrl && assignment.status !== AssignmentStatus.COMPLETED"
        :href="mapsUrl"
        target="_blank"
        variant="outlined"
        prepend-icon="mdi-google-maps"
        color="primary"
        block
        size="default"
        class="mb-2"
      >
        Ver en Google Maps
      </v-btn>

      <!-- Cancel -->
      <v-btn
        v-if="assignment.status !== AssignmentStatus.COMPLETED && assignment.status !== AssignmentStatus.CANCELLED"
        variant="text"
        color="error"
        prepend-icon="mdi-close-circle"
        block
        size="small"
        @click="cancel"
      >
        Cancelar asignación
      </v-btn>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.assignment-card {
  border: 1px solid rgb(var(--v-theme-primary), 0.4);
}
.mt-0-5 {
  margin-top: 2px;
}
</style>
