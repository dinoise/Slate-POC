<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute as useVueRoute, useRouter } from 'vue-router'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useReporterSessionStore } from '@/stores/reporterSession'
import { useIncidentSSE, useRoute } from '@slate/composables'
import { adjustersApi } from '@slate/api-client'
import type { Adjuster } from '@slate/types'
import { AssignmentStatus, TERMINAL_ASSIGNMENT_STATUSES } from '@slate/types'

const { decodePolyline } = useRoute()

const vueRoute = useVueRoute()
const router = useRouter()
const store = useReporterSessionStore()

const incidentId = computed(() => Number(vueRoute.params['id']))

// ── SSE ───────────────────────────────────────────────────────────────────────
const { event: sseEvent, connected } = useIncidentSSE(incidentId)

watch(sseEvent, (ev) => {
  if (!ev) return
  store.applySSEEvent(ev)

  // Draw route from SSE polyline (already decoded by notifications enricher)
  if (ev.route_polyline && map) {
    drawPolyline(decodePolyline(ev.route_polyline))
  }

  // Clear route and adjuster marker on terminal status
  if (ev.status === AssignmentStatus.CANCELLED || ev.status === AssignmentStatus.COMPLETED) {
    if (map) {
      if (routeLine) { map.removeLayer(routeLine); routeLine = null }
      if (adjusterMarker) { map.removeLayer(adjusterMarker); adjusterMarker = null }
    }
  }
})

// ── Map ───────────────────────────────────────────────────────────────────────
const mapContainer = ref<HTMLElement>()
let map: L.Map | null = null
let incidentMarker: L.Marker | null = null
let adjusterMarker: L.Marker | null = null
let routeLine: L.Polyline | null = null

const incIcon = L.divIcon({
  html: '<div style="font-size:28px;line-height:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,.5));">📍</div>',
  iconSize: [28, 28],
  iconAnchor: [14, 28],
  className: '',
})
const adjIcon = L.divIcon({
  html: '<div style="font-size:28px;line-height:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,.5));">🔵</div>',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  className: '',
})

onMounted(async () => {
  if (!mapContainer.value) return
  map = L.map(mapContainer.value).setView([19.4326, -99.1332], 12)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CartoDB',
    maxZoom: 19,
  }).addTo(map)

  await store.loadIncident(incidentId.value)
})

onUnmounted(() => {
  map?.remove()
  map = null
})

// ── Adjuster info ─────────────────────────────────────────────────────────────
const adjuster = ref<Adjuster | null>(null)

watch(
  () => store.assignment,
  async (asgn) => {
    if (!asgn) return
    // Only fetch adjuster info once (first assignment or adjuster change)
    if (!adjuster.value || adjuster.value.id !== asgn.adjuster_id) {
      try {
        adjuster.value = await adjustersApi.get(asgn.adjuster_id)
      } catch {
        // silent
      }
    }
    updateMap()
  },
)

watch(() => store.incident, () => updateMap())

function drawPolyline(coords: [number, number][]) {
  if (!map || coords.length < 2) return
  if (routeLine) { map.removeLayer(routeLine); routeLine = null }
  routeLine = L.polyline(coords, { color: '#f59e0b', weight: 4, opacity: 0.85 }).addTo(map)
  const bounds = routeLine.getBounds()
  if (bounds.isValid()) map.fitBounds(bounds, { padding: [60, 60] })
}

function updateMap() {
  if (!map) return
  const inc = store.incident
  const asgn = store.assignment
  const adj = adjuster.value

  if (inc) {
    if (incidentMarker) map.removeLayer(incidentMarker)
    incidentMarker = L.marker([inc.latitude, inc.longitude], { icon: incIcon })
      .bindTooltip('Siniestro', { permanent: false })
      .addTo(map)
    map.setView([inc.latitude, inc.longitude], 14)
  }

  if (adj && asgn) {
    const adjLat = adj.current_latitude ?? adj.home_latitude
    const adjLon = adj.current_longitude ?? adj.home_longitude

    if (adjusterMarker) map.removeLayer(adjusterMarker)
    adjusterMarker = L.marker([adjLat, adjLon], { icon: adjIcon })
      .bindTooltip(`${adj.first_name} ${adj.last_name}`, { permanent: false })
      .addTo(map)

    // Draw polyline from stored assignment if available, else straight dashed fallback
    if (asgn.route_polyline) {
      drawPolyline(decodePolyline(asgn.route_polyline))
    } else if (inc && !routeLine) {
      // Fallback straight line only if no polyline has been drawn yet
      routeLine = L.polyline(
        [[adjLat, adjLon], [inc.latitude, inc.longitude]],
        { color: '#f59e0b', weight: 2, dashArray: '6 8', opacity: 0.7 },
      ).addTo(map)
      const bounds = routeLine.getBounds()
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [60, 60] })
    }
  }
}

// ── Status display ────────────────────────────────────────────────────────────
const statusConfig: Record<string, { label: string; badge: string; emoji: string }> = {
  pending:                          { label: 'Pendiente',           badge: 'badge-warning', emoji: '⏳' },
  [AssignmentStatus.ASSIGNED]:      { label: 'Ajustador asignado',  badge: 'badge-primary', emoji: '✅' },
  [AssignmentStatus.ACCEPTED]:      { label: 'Ajustador en camino', badge: 'badge-primary', emoji: '🚗' },
  [AssignmentStatus.EN_ROUTE]:      { label: 'Ajustador en camino', badge: 'badge-primary', emoji: '🚗' },
  [AssignmentStatus.ARRIVED]:       { label: 'Llegó al siniestro',  badge: 'badge-success', emoji: '📍' },
  [AssignmentStatus.IN_PROGRESS]:   { label: 'Atendiendo',          badge: 'badge-success', emoji: '🔧' },
  [AssignmentStatus.COMPLETED]:     { label: 'Completado',          badge: 'badge-success', emoji: '✔️' },
  [AssignmentStatus.CANCELLED]:     { label: 'Cancelado',           badge: 'badge-error',   emoji: '✖️' },
}

const incidentStatus = computed(() => store.incident?.status ?? 'pending')
const assignmentStatus = computed(() => store.assignment?.status ?? null)

const displayStatus = computed(() => {
  const s = assignmentStatus.value ?? incidentStatus.value
  return statusConfig[s] ?? { label: s, badge: 'badge-neutral', emoji: '•' }
})

const hasAdjuster = computed(() => !!store.assignment && !!adjuster.value)
const isTerminal = computed(() =>
  store.assignment ? TERMINAL_ASSIGNMENT_STATUSES.has(store.assignment.status) : false,
)

// Toast on each status transition
const statusToast = ref<string | null>(null)
watch(assignmentStatus, (newStatus, oldStatus) => {
  if (!newStatus || newStatus === oldStatus) return
  const cfg = statusConfig[newStatus]
  if (cfg) {
    statusToast.value = `${cfg.emoji} ${cfg.label}`
    setTimeout(() => { statusToast.value = null }, 4_000)
  }
})

function formatETA(isoDate: string | null | undefined): string {
  if (!isoDate) return '—'
  return new Intl.DateTimeFormat('es-MX', { hour: '2-digit', minute: '2-digit' }).format(new Date(isoDate))
}

function formatDistance(km: number | null | undefined): string {
  if (km == null) return '—'
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1)} km`
}

async function cancel() {
  await store.cancelIncident()
  router.push('/report')
}
</script>

<template>
  <div class="reporter-layout">
    <!-- Top nav -->
    <div class="navbar bg-base-100 shadow-sm px-4 min-h-12">
      <div class="flex-none mr-2">
        <button class="btn btn-ghost btn-circle btn-sm" @click="router.push('/report')">
          ←
        </button>
      </div>
      <div class="flex-1">
        <span class="text-sm font-bold">Seguimiento #{{ incidentId }}</span>
      </div>
      <!-- SSE connection indicator -->
      <div class="flex-none">
        <span
          :class="['badge badge-xs', connected ? 'badge-success' : 'badge-warning']"
          :title="connected ? 'Conectado' : 'Reconectando…'"
        >
          {{ connected ? '● En vivo' : '○ Reconectando' }}
        </span>
      </div>
    </div>

    <!-- Map -->
    <div ref="mapContainer" class="track-map" />

    <!-- Info panel (bottom card) -->
    <div class="absolute bottom-0 left-0 right-0 z-[500]">
      <div class="bg-base-100 rounded-t-2xl shadow-2xl p-4 flex flex-col gap-3">

        <!-- Loading -->
        <div v-if="store.loading && !store.incident" class="flex justify-center py-4">
          <span class="loading loading-spinner loading-md text-primary" />
        </div>

        <template v-else-if="store.incident">
          <!-- Status badge + type -->
          <div class="flex items-center gap-2">
            <span class="text-lg">{{ displayStatus.emoji }}</span>
            <span :class="['badge', displayStatus.badge]">{{ displayStatus.label }}</span>
            <span class="text-sm text-base-content/60 ml-auto capitalize">
              {{ store.incident.incident_type.replace('_', ' ') }}
            </span>
          </div>

          <!-- Address -->
          <p class="text-sm text-base-content/70 leading-snug line-clamp-2">
            📍 {{ store.incident.address }}
          </p>

          <!-- Adjuster info (when assigned) -->
          <div v-if="hasAdjuster && adjuster" class="card bg-base-200 rounded-xl p-3 flex flex-row gap-3 items-center">
            <div class="avatar placeholder flex-none">
              <div class="bg-primary text-primary-content rounded-full w-10">
                <span class="text-base">{{ adjuster.first_name.charAt(0) }}{{ adjuster.last_name.charAt(0) }}</span>
              </div>
            </div>
            <div class="flex-1 min-w-0">
              <p class="font-semibold text-sm truncate">{{ adjuster.first_name }} {{ adjuster.last_name }}</p>
              <p v-if="adjuster.phone" class="text-xs text-base-content/60 truncate">{{ adjuster.phone }}</p>
            </div>
            <div class="text-right flex-none">
              <p class="text-xs text-base-content/50">ETA</p>
              <p class="text-sm font-semibold text-primary">
                {{ formatETA(store.assignment?.estimated_arrival_time) }}
              </p>
              <p class="text-xs text-base-content/50">
                {{ formatDistance(store.assignment?.distance_km) }}
              </p>
            </div>
          </div>

          <!-- Waiting for adjuster -->
          <div v-else-if="!isTerminal" class="flex items-center gap-2 text-sm text-base-content/60">
            <span class="loading loading-dots loading-xs" />
            Buscando ajustador disponible…
          </div>

          <!-- Error -->
          <div v-if="store.error" role="alert" class="alert alert-error text-sm py-2">
            <span>{{ store.error }}</span>
          </div>

          <!-- Actions -->
          <div v-if="!isTerminal" class="flex gap-2 pt-1">
            <button
              class="btn btn-error btn-outline btn-sm flex-1"
              :disabled="store.loading"
              @click="cancel"
            >
              Cancelar reporte
            </button>
          </div>

          <div v-else class="flex gap-2 pt-1">
            <button class="btn btn-primary btn-sm flex-1" @click="router.push('/report')">
              Nuevo reporte
            </button>
          </div>
        </template>

        <!-- Error loading -->
        <div v-else-if="store.error" role="alert" class="alert alert-error text-sm">
          <span>{{ store.error }}</span>
          <button class="btn btn-ghost btn-xs" @click="router.push('/report')">Volver</button>
        </div>
      </div>
    </div>

    <!-- Status change toast -->
    <div v-if="statusToast" class="toast toast-top toast-center z-[600]">
      <div class="alert alert-info shadow-lg text-sm font-medium">
        <span>{{ statusToast }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reporter-layout {
  position: relative;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.track-map {
  flex: 1;
  min-height: 0;
}
</style>
