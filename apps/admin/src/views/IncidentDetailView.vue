<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import Card from 'primevue/card'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import Tag from 'primevue/tag'
import { incidentsApi, assignmentsApi } from '@slate/api-client'
import { useIncidentSSE, useRoute as useRouteComposable, formatMXDate } from '@slate/composables'
import type { Incident, Assignment } from '@slate/types'
import { AssignmentStatus } from '@slate/types'
import EmptyState from '../components/EmptyState.vue'

const route = useRoute()
const router = useRouter()
const { decodePolyline } = useRouteComposable()

const incidentId = computed(() => Number(route.params.id))

const incident = ref<Incident | null>(null)
const assignments = ref<Assignment[]>([])
const activeAssignment = computed(() =>
  assignments.value.find((a) => !['cancelled', 'completed'].includes(a.status)) ?? null,
)
const loading = ref(true)
const error = ref<string | null>(null)
const cancelling = ref(false)

async function cancelIncident() {
  if (!incident.value) return
  cancelling.value = true
  error.value = null
  try {
    await incidentsApi.delete(incident.value.id)
    router.push('/incidents')
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al cancelar incidente'
    cancelling.value = false
  }
}

// ── Assignment timeline ───────────────────────────────────────────────────────

const ASSIGNMENT_STEPS: Assignment['status'][] = [
  'assigned', 'accepted', 'en_route', 'arrived', 'in_progress', 'completed',
]

const stepLabel: Record<string, string> = {
  assigned:    'Asignado',
  accepted:    'Aceptado',
  en_route:    'En camino',
  arrived:     'Llegó',
  in_progress: 'En atención',
  completed:   'Completado',
  cancelled:   'Cancelado',
}

function stepSeverity(step: string, current: string): 'success' | 'secondary' | 'warn' {
  const stepIdx = ASSIGNMENT_STEPS.indexOf(step as Assignment['status'])
  const currentIdx = ASSIGNMENT_STEPS.indexOf(current as Assignment['status'])
  if (current === 'completed') return 'success'   // all steps green when completed
  if (stepIdx < currentIdx) return 'success'
  if (stepIdx === currentIdx) return 'warn'
  return 'secondary'
}

// ── SSE — real-time status updates ───────────────────────────────────────────

const { event: sseEvent } = useIncidentSSE(incidentId)

watch(sseEvent, (ev) => {
  if (!ev || !ev.assignment_id) return

  // Update the matching assignment's status in-place
  const hit = assignments.value.find((a) => a.id === ev.assignment_id)
  if (hit) hit.status = ev.status as AssignmentStatus

  // Update incident status from SSE event
  if (incident.value) {
    incident.value = {
      ...incident.value,
      status: ['completed', 'cancelled'].includes(ev.status)
        ? ev.status as Incident['status']
        : incident.value.status,
    }
  }

  // Update map with new polyline if available
  if (ev.route?.polyline) drawPolyline(decodePolyline(ev.route.polyline))

  // Clear route on terminal
  if (ev.status === AssignmentStatus.CANCELLED || ev.status === AssignmentStatus.COMPLETED) {
    if (map && routeLine) { map.removeLayer(routeLine); routeLine = null }
  }
})

// ── Map ───────────────────────────────────────────────────────────────────────

const mapContainer = ref<HTMLElement>()
let map: L.Map | null = null
let incidentMarker: L.Marker | null = null
let routeLine: L.Polyline | null = null

const incIcon = L.divIcon({
  html: '<div style="font-size:26px;line-height:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,.4));">📍</div>',
  iconSize: [26, 26], iconAnchor: [13, 26], className: '',
})

function initMap() {
  if (!mapContainer.value || map) return
  map = L.map(mapContainer.value).setView([19.4326, -99.1332], 12)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CartoDB',
    maxZoom: 19,
  }).addTo(map)
  updateMapMarkers()
}

function updateMapMarkers() {
  if (!map || !incident.value) return
  const inc = incident.value
  const asgn = activeAssignment.value

  if (incidentMarker) map.removeLayer(incidentMarker)
  incidentMarker = L.marker([inc.latitude, inc.longitude], { icon: incIcon })
    .bindTooltip('Siniestro').addTo(map)

  if (asgn?.route_polyline) {
    drawPolyline(decodePolyline(asgn.route_polyline))
  } else {
    map.setView([inc.latitude, inc.longitude], 14)
  }
}

function drawPolyline(coords: [number, number][]) {
  if (!map || coords.length < 2) return
  if (routeLine) { map.removeLayer(routeLine); routeLine = null }
  routeLine = L.polyline(coords, { color: '#f59e0b', weight: 4, opacity: 0.85 }).addTo(map)
  const bounds = routeLine.getBounds()
  if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] })
}

onUnmounted(() => { map?.remove(); map = null })

// ── Load data ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  const id = incidentId.value
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
    // Init map after data loaded so incident coords are available
    await new Promise((r) => requestAnimationFrame(r))
    initMap()
  }
})

// ── Status display helpers ────────────────────────────────────────────────────

const INCIDENT_STATUS_LABELS: Record<string, string> = {
  pending:     'Pendiente',
  assigned:    'Asignado',
  completed:   'Completado',
  cancelled:   'Cancelado',
}

const incidentStatusSeverity = computed((): 'warn' | 'success' | 'danger' | 'secondary' => {
  switch (incident.value?.status) {
    case 'completed':  return 'success'
    case 'cancelled':  return 'danger'
    case 'assigned':   return 'warn'
    default:           return 'secondary'
  }
})

const severityLabelMap: Record<number, string> = { 1: 'Muy leve', 2: 'Leve', 3: 'Moderado', 4: 'Grave', 5: 'Crítico' }
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
      <Button
        v-if="incident && !['cancelled', 'completed'].includes(incident.status)"
        icon="pi pi-times-circle"
        label="Cancelar incidente"
        severity="danger"
        :loading="cancelling"
        class="ml-auto"
        @click="cancelIncident"
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
          <Tag :value="`Severidad ${incident.severity}`" severity="secondary" />
          <Tag
            :value="INCIDENT_STATUS_LABELS[incident.status] ?? incident.status"
            :severity="incidentStatusSeverity"
          />
        </div>
      </div>

      <!-- Map + Info grid -->
      <div class="detail-grid-top">
        <!-- Map -->
        <Card class="map-card">
          <template #content>
            <div ref="mapContainer" class="detail-map" />
          </template>
        </Card>

        <!-- Info del incidente -->
        <Card>
          <template #title>Información</template>
          <template #content>
            <dl class="info-list">
              <div class="info-row">
                <dt>Tipo</dt>
                <dd>{{ incident.incident_type.replace(/_/g, ' ') }}</dd>
              </div>
              <div class="info-row">
                <dt>Severidad</dt>
                <dd>{{ severityLabelMap[incident.severity] ?? incident.severity }}</dd>
              </div>
              <div class="info-row">
                <dt>Descripción</dt>
                <dd>{{ incident.description || '—' }}</dd>
              </div>
              <div class="info-row">
                <dt>Coordenadas</dt>
                <dd>{{ incident.latitude.toFixed(5) }}, {{ incident.longitude.toFixed(5) }}</dd>
              </div>
              <div class="info-row">
                <dt>Creado</dt>
                <dd>{{ formatMXDate(incident.created_at) }}</dd>
              </div>
              <div class="info-row">
                <dt>Actualizado</dt>
                <dd>{{ formatMXDate(incident.updated_at) }}</dd>
              </div>
            </dl>
          </template>
        </Card>
      </div>

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
              <div v-if="asgn.status !== 'cancelled'" class="timeline">
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
                <span v-if="asgn.route_distance_m ?? asgn.distance_km">
                  {{ asgn.route_distance_m ? (asgn.route_distance_m / 1000).toFixed(1) : asgn.distance_km?.toFixed(1) }} km
                </span>
                <span v-if="asgn.route_duration_s ?? asgn.travel_time_minutes">
                  {{ asgn.route_duration_s ? Math.round(asgn.route_duration_s / 60) : asgn.travel_time_minutes }} min
                </span>
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
  justify-content: space-between;
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

.detail-grid-top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .detail-grid-top { grid-template-columns: 1fr; }
}

.map-card :deep(.p-card-body),
.map-card :deep(.p-card-content) {
  padding: 0;
  height: 100%;
}

.detail-map {
  height: 280px;
  border-radius: 8px;
  overflow: hidden;
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
.timeline-step--warn .timeline-dot    { background: var(--p-yellow-400); }

.timeline-label {
  font-size: 0.6rem;
  color: var(--p-surface-400);
  margin-top: 0.3rem;
  text-align: center;
}

.timeline-step--success .timeline-label { color: var(--p-green-400); }
.timeline-step--warn .timeline-label    { color: var(--p-yellow-400); }

.assignment-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  font-size: 0.8rem;
  color: var(--p-surface-400);
}
</style>
