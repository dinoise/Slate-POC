<script setup lang="ts">
import { ref, watch, computed, onMounted, onUnmounted } from 'vue'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import 'leaflet-ant-path'
import { useSSE } from '@slate/composables'
import { useRoute } from '@slate/composables'
import { useAdjusterSessionStore } from '@/stores/adjusterSession'
import AdjusterSelector from '@/components/AdjusterSelector.vue'
import AssignmentCard from '@/components/AssignmentCard.vue'
import NewAssignmentBanner from '@/components/NewAssignmentBanner.vue'
import type { AssignmentEvent } from '@slate/types'

const store = useAdjusterSessionStore()
const { buildRouteLayer, removeRouteLayer, fetchRoute, routeFromPayload } = useRoute()

// ── Map ───────────────────────────────────────────────────────────────────────
const mapContainer = ref<HTMLElement>()
let map: L.Map | null = null
let adjusterMarker: L.Marker | null = null
let incidentMarker: L.Marker | null = null
let routeLayer: L.Layer | null = null
let routeColorIndex = 0

const adjIcon = L.divIcon({
  html: '<div style="font-size:26px;line-height:1;">🔵</div>',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  className: '',
})
const incIcon = L.divIcon({
  html: '<div style="font-size:26px;line-height:1;">🔴</div>',
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  className: '',
})

onMounted(() => {
  if (!mapContainer.value) return
  map = L.map(mapContainer.value).setView([19.4326, -99.1332], 11)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CartoDB',
    maxZoom: 19,
  }).addTo(map)
})

onUnmounted(() => {
  map?.remove()
  map = null
})

function clearMap() {
  if (!map) return
  if (adjusterMarker) { map.removeLayer(adjusterMarker); adjusterMarker = null }
  if (incidentMarker) { map.removeLayer(incidentMarker); incidentMarker = null }
  if (routeLayer) { removeRouteLayer(map, routeLayer); routeLayer = null }
}

async function drawRoute(
  adjLat: number, adjLon: number,
  incLat: number, incLon: number,
) {
  if (!map) return
  if (routeLayer) { removeRouteLayer(map, routeLayer); routeLayer = null }

  try {
    const result = await fetchRoute(adjLat, adjLon, incLat, incLon)
    if (!map) return
    routeLayer = buildRouteLayer(L, result.coords, result.traffic_segments, routeColorIndex++)
    routeLayer!.addTo(map)
    const bounds = (routeLayer as L.Polyline).getBounds?.()
    if (bounds?.isValid()) map.fitBounds(bounds, { padding: [40, 40] })
  } catch {
    // Fallback: straight dashed line
    if (!map) return
    routeLayer = L.polyline([[adjLat, adjLon], [incLat, incLon]], {
      color: '#f59e0b', weight: 3, dashArray: '8 8',
    }).addTo(map)
    map.fitBounds((routeLayer as L.Polyline).getBounds(), { padding: [40, 40] })
  }
}

// ── React to adjuster selection ───────────────────────────────────────────────
watch(
  () => store.adjuster,
  (adj) => {
    clearMap()
    if (!adj || !map) return
    const adjLat = adj.current_latitude ?? adj.home_latitude
    const adjLon = adj.current_longitude ?? adj.home_longitude
    if (adjLat && adjLon) {
      adjusterMarker = L.marker([adjLat, adjLon], { icon: adjIcon })
        .bindTooltip(`${adj.first_name} ${adj.last_name}`, { permanent: false })
        .addTo(map)
      map.setView([adjLat, adjLon], 13)
    }
  },
)

// ── React to active assignment ────────────────────────────────────────────────
// Holds enriched incident info from SSE or initial load
const incidentMeta = ref<{
  type: string | null
  address: string | null
  lat: number | null
  lon: number | null
  severity: number | null
}>({ type: null, address: null, lat: null, lon: null, severity: null })

watch(
  () => store.activeAssignment,
  async (assignment) => {
    if (!map || !assignment) {
      if (incidentMarker && map) { map.removeLayer(incidentMarker); incidentMarker = null }
      if (routeLayer && map) { removeRouteLayer(map, routeLayer); routeLayer = null }
      return
    }
    // Assignment loaded from REST — incidentMeta may need fetching
    // If already set via SSE event keep it; otherwise use what we have
    if (!incidentMeta.value.lat) return

    const adj = store.adjuster
    const { lat, lon } = incidentMeta.value
    if (!adj || !lat || !lon) return

    // Place incident marker
    if (incidentMarker) map.removeLayer(incidentMarker)
    incidentMarker = L.marker([lat, lon], { icon: incIcon })
      .bindTooltip(incidentMeta.value.type ?? 'Siniestro')
      .addTo(map)

    // Draw route
    const adjLat = adj.current_latitude ?? adj.home_latitude
    const adjLon = adj.current_longitude ?? adj.home_longitude
    if (adjLat && adjLon) {
      await drawRoute(adjLat, adjLon, lat, lon)
    }
  },
)

// ── SSE ───────────────────────────────────────────────────────────────────────
const adjusterId = computed(() => store.adjusterId)
const { events, connected } = useSSE(adjusterId)

const latestEvent = ref<AssignmentEvent | null>(null)

watch(events, async (evts) => {
  const ev = evts[0]
  if (!ev) return
  latestEvent.value = ev

  // Update incident meta from SSE payload (already enriched by notifications service)
  incidentMeta.value = {
    type: ev.incident_type ?? null,
    address: ev.address ?? null,
    lat: ev.latitude ?? null,
    lon: ev.longitude ?? null,
    severity: typeof ev.severity === 'number' ? ev.severity : null,
  }

  // Place marker and draw route
  if (!map) return
  const adj = store.adjuster
  if (ev.latitude && ev.longitude) {
    if (incidentMarker) map.removeLayer(incidentMarker)
    incidentMarker = L.marker([ev.latitude, ev.longitude], { icon: incIcon })
      .bindTooltip(ev.incident_type ?? 'Siniestro')
      .addTo(map)

    const adjLat = adj?.current_latitude ?? adj?.home_latitude
    const adjLon = adj?.current_longitude ?? adj?.home_longitude
    if (adjLat && adjLon) {
      if (ev.route_polyline) {
        // Fast path: polyline already embedded in the SSE payload — no extra fetch needed
        if (routeLayer) { removeRouteLayer(map, routeLayer); routeLayer = null }
        const result = routeFromPayload(ev.route_polyline, ev.route_distance_m, ev.route_duration_s)
        routeLayer = buildRouteLayer(L, result.coords, result.traffic_segments, routeColorIndex++)
        routeLayer!.addTo(map)
        const bounds = (routeLayer as L.Polyline).getBounds?.()
        if (bounds?.isValid()) map.fitBounds(bounds, { padding: [40, 40] })
      } else {
        // Fallback: route not yet fetched — call route API
        await drawRoute(adjLat, adjLon, ev.latitude, ev.longitude)
      }
    }
  }

  // Reload active assignment to update store
  if (store.adjuster) {
    await store.loadActiveAssignment(store.adjuster.id)
  }
})

// SSE badge color
const sseBadgeColor = computed(() => {
  if (!store.adjuster) return 'grey'
  return connected.value ? 'success' : 'warning'
})
const sseBadgeText = computed(() => {
  if (!store.adjuster) return 'Sin conexión'
  return connected.value ? 'Conectado' : 'Reconectando…'
})
</script>

<template>
  <v-app-bar color="surface" elevation="1" density="compact">
    <v-app-bar-title>
      <span class="text-body-1 font-weight-bold">Vista Ajustador</span>
    </v-app-bar-title>
    <template #append>
      <v-chip
        :color="sseBadgeColor"
        size="x-small"
        class="mr-2"
        label
      >
        {{ sseBadgeText }}
      </v-chip>
    </template>
  </v-app-bar>

  <v-main>
    <div class="adjuster-layout">
      <!-- Sidebar / top panel -->
      <div class="adjuster-sidebar">
        <!-- Adjuster selector -->
        <div class="pa-3">
          <AdjusterSelector />
        </div>

        <!-- Adjuster info chip -->
        <div v-if="store.adjuster" class="px-3 pb-2">
          <v-chip
            :color="store.adjuster.status === 'available' ? 'success' : ['busy', 'en_route', 'on_site'].includes(store.adjuster.status) ? 'warning' : 'grey'"
            size="small"
            prepend-icon="mdi-account-hard-hat"
            label
          >
            {{ store.adjuster.first_name }} {{ store.adjuster.last_name }}
          </v-chip>
        </div>

        <!-- Error state -->
        <v-alert
          v-if="store.error"
          type="error"
          density="compact"
          class="mx-3 mb-2"
          closable
        >
          {{ store.error }}
        </v-alert>

        <!-- No adjuster selected -->
        <div v-if="!store.adjuster && !store.loading" class="px-3 pb-3">
          <v-card color="surface" variant="tonal" rounded="lg">
            <v-card-text class="text-center text-medium-emphasis py-4">
              <v-icon size="32" class="mb-2">mdi-account-question</v-icon>
              <div class="text-body-2">Selecciona un ajustador para conectarte al stream de notificaciones</div>
            </v-card-text>
          </v-card>
        </div>

        <!-- Loading -->
        <div v-if="store.loading" class="px-3 pb-3 text-center">
          <v-progress-circular indeterminate color="primary" size="24" />
        </div>

        <!-- Active assignment card -->
        <div v-if="store.activeAssignment" class="px-3 pb-3">
          <AssignmentCard
            :assignment="store.activeAssignment"
            :incident-lat="incidentMeta.lat"
            :incident-lon="incidentMeta.lon"
            :incident-type="incidentMeta.type"
            :incident-address="incidentMeta.address"
            :severity="incidentMeta.severity"
          />
        </div>

        <!-- Waiting state -->
        <div
          v-else-if="store.adjuster && !store.loading"
          class="px-3 pb-3"
        >
          <v-card color="surface" variant="tonal" rounded="lg">
            <v-card-text class="text-center py-4">
              <v-icon size="32" color="primary" class="mb-2">mdi-clock-outline</v-icon>
              <div class="text-body-2 text-medium-emphasis">Esperando asignaciones…</div>
            </v-card-text>
          </v-card>
        </div>
      </div>

      <!-- Map -->
      <div ref="mapContainer" class="adjuster-map" />
    </div>
  </v-main>

  <!-- SSE new assignment banner -->
  <NewAssignmentBanner :event="latestEvent" />
</template>

<style scoped>
.adjuster-layout {
  display: flex;
  flex-direction: column;
  height: calc(100dvh - 48px); /* dvh = dynamic viewport height (respects mobile browser chrome) */
}

.adjuster-sidebar {
  overflow-y: auto;
  flex-shrink: 0;
  max-height: 45dvh;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.adjuster-map {
  flex: 1;
  min-height: 0;
}

/* Desktop: side-by-side */
@media (min-width: 768px) {
  .adjuster-layout {
    flex-direction: row;
  }
  .adjuster-sidebar {
    width: 320px;
    max-height: none;
    height: 100%;
    border-bottom: none;
    border-right: 1px solid rgba(255, 255, 255, 0.08);
    overflow-y: auto;
  }
  .adjuster-map {
    flex: 1;
    height: 100%;
  }
}
</style>
