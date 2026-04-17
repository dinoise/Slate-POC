<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import { incidentsApi, assignmentsApi } from '@slate/api-client'
import type { Incident, Assignment } from '@slate/types'
import EmptyState from '../components/EmptyState.vue'

const route = useRoute()
const router = useRouter()

const incident = ref<Incident | null>(null)
const assignments = ref<Assignment[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const ASSIGNMENT_STEPS: Assignment['status'][] = [
  'pending', 'assigned', 'accepted', 'en_route', 'arrived', 'completed',
]

const stepLabel: Record<string, string> = {
  pending: 'Pendiente',
  assigned: 'Asignado',
  accepted: 'Aceptado',
  en_route: 'En camino',
  arrived: 'Llegó',
  completed: 'Completado',
  cancelled: 'Cancelado',
}

const severityMap: Record<string, string> = {
  critical: 'danger', high: 'warn', medium: 'info', low: 'secondary',
}

const statusMap: Record<string, string> = {
  open: 'danger', in_progress: 'warn', resolved: 'success',
}

function stepSeverity(step: string, current: string): 'success' | 'secondary' | 'warn' {
  const stepIdx = ASSIGNMENT_STEPS.indexOf(step as Assignment['status'])
  const currentIdx = ASSIGNMENT_STEPS.indexOf(current as Assignment['status'])
  if (stepIdx < currentIdx) return 'success'
  if (stepIdx === currentIdx) return 'warn'
  return 'secondary'
}

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [inc, asgns] = await Promise.all([
      incidentsApi.get(id),
      assignmentsApi.byIncident(id),
    ])
    incident.value = inc
    assignments.value = Array.isArray(asgns) ? asgns : []
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al cargar incidente'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="incident-detail">
    <!-- Toolbar -->
    <div class="detail-toolbar">
      <Button
        icon="pi pi-arrow-left"
        label="Incidentes"
        severity="secondary"
        text
        @click="router.push('/incidents')"
      />
    </div>

    <!-- Loading -->
    <div v-if="loading" class="detail-loading">
      <ProgressSpinner />
    </div>

    <!-- Error -->
    <EmptyState v-else-if="error" icon="pi-exclamation-circle" :error="error" />

    <template v-else-if="incident">
      <!-- Header -->
      <div class="detail-header">
        <div>
          <h1 class="detail-title">Incidente #{{ incident.id }}</h1>
          <p class="detail-subtitle">{{ incident.address }}</p>
        </div>
        <div class="detail-badges">
          <Badge :value="incident.severity" :severity="severityMap[incident.severity] ?? 'info'" />
          <Badge :value="incident.status" :severity="statusMap[incident.status] ?? 'info'" />
        </div>
      </div>

      <div class="detail-grid">
        <!-- Info del incidente -->
        <Card>
          <template #title>Información</template>
          <template #content>
            <dl class="info-list">
              <div class="info-row">
                <dt>Tipo</dt>
                <dd>{{ incident.incident_type }}</dd>
              </div>
              <div class="info-row">
                <dt>Descripción</dt>
                <dd>{{ incident.description || '—' }}</dd>
              </div>
              <div class="info-row">
                <dt>Reportante</dt>
                <dd>{{ incident.reporter_name }}</dd>
              </div>
              <div class="info-row">
                <dt>Email</dt>
                <dd>{{ incident.reporter_email }}</dd>
              </div>
              <div class="info-row">
                <dt>Coordenadas</dt>
                <dd>{{ incident.latitude }}, {{ incident.longitude }}</dd>
              </div>
              <div class="info-row">
                <dt>Creado</dt>
                <dd>{{ new Date(incident.created_at).toLocaleString('es-MX') }}</dd>
              </div>
              <div class="info-row">
                <dt>Actualizado</dt>
                <dd>{{ new Date(incident.updated_at).toLocaleString('es-MX') }}</dd>
              </div>
            </dl>
          </template>
        </Card>

        <!-- Historial de asignaciones -->
        <Card>
          <template #title>Asignaciones ({{ assignments.length }})</template>
          <template #content>
            <EmptyState
              v-if="assignments.length === 0"
              icon="pi-link"
              title="Sin asignaciones"
              message="Este incidente no tiene ajustadores asignados aún."
            />
            <div v-else class="assignments-list">
              <div
                v-for="asgn in assignments"
                :key="asgn.id"
                class="assignment-item"
              >
                <div class="assignment-header">
                  <span class="assignment-id">Asignación #{{ asgn.id }}</span>
                  <Tag
                    :value="stepLabel[asgn.status] ?? asgn.status"
                    :severity="asgn.status === 'completed' ? 'success' : asgn.status === 'cancelled' ? 'danger' : 'warn'"
                  />
                </div>

                <!-- Timeline de pasos -->
                <div class="timeline">
                  <div
                    v-for="step in ASSIGNMENT_STEPS"
                    :key="step"
                    class="timeline-step"
                    :class="`timeline-step--${stepSeverity(step, asgn.status)}`"
                  >
                    <div class="timeline-dot" />
                    <span class="timeline-label">{{ stepLabel[step] }}</span>
                  </div>
                </div>

                <div class="assignment-meta">
                  <span v-if="asgn.distance_km">{{ asgn.distance_km }} km</span>
                  <span v-if="asgn.travel_time_minutes">{{ asgn.travel_time_minutes }} min</span>
                  <span>Ajustador #{{ asgn.adjuster_id }}</span>
                  <Button
                    icon="pi pi-user"
                    size="small"
                    severity="secondary"
                    text
                    rounded
                    @click="router.push(`/adjusters/${asgn.adjuster_id}`)"
                  />
                </div>
              </div>
            </div>
          </template>
        </Card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.incident-detail {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.detail-loading {
  display: flex;
  justify-content: center;
  padding: 4rem;
}

.detail-toolbar {
  display: flex;
  align-items: center;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
}

.detail-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
}

.detail-subtitle {
  font-size: 0.9rem;
  color: var(--p-surface-400);
  margin-top: 0.25rem;
}

.detail-badges {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .detail-grid { grid-template-columns: 1fr; }
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.info-row {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.info-row dt {
  color: var(--p-surface-400);
  font-weight: 500;
}

.info-row dd {
  color: var(--p-surface-100);
}

.assignments-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.assignment-item {
  border: 1px solid var(--p-surface-700);
  border-radius: 8px;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.assignment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.assignment-id {
  font-weight: 600;
  color: var(--p-surface-200);
  font-size: 0.9rem;
}

.timeline {
  display: flex;
  gap: 0;
  align-items: center;
}

.timeline-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  position: relative;
}

.timeline-step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 7px;
  left: 50%;
  width: 100%;
  height: 2px;
  background: var(--p-surface-600);
  z-index: 0;
}

.timeline-step--success::after { background: var(--p-green-600); }

.timeline-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--p-surface-600);
  z-index: 1;
  position: relative;
}

.timeline-step--success .timeline-dot { background: var(--p-green-400); }
.timeline-step--warn .timeline-dot { background: var(--p-yellow-400); }

.timeline-label {
  font-size: 0.65rem;
  color: var(--p-surface-400);
  margin-top: 0.3rem;
  text-align: center;
}

.timeline-step--success .timeline-label { color: var(--p-green-400); }
.timeline-step--warn .timeline-label { color: var(--p-yellow-400); }

.assignment-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: var(--p-surface-400);
}
</style>
