<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import Card from 'primevue/card'
import Button from 'primevue/button'
import Select from 'primevue/select'
import Drawer from 'primevue/drawer'
import Slider from 'primevue/slider'
import ProgressSpinner from 'primevue/progressspinner'
import Badge from 'primevue/badge'

import { useObservatorySSE, useObservatoryMap, getMXCurrentSlot, formatMXDate } from '@slate/composables'
import { demandApi, recommendationsApi } from '@slate/api-client'
import type { DemandPrediction, RecommendationResponse } from '@slate/types'

// ── SSE ───────────────────────────────────────────────────────────────────────
const { activeAssignments, assignments, connected, lastEventAt, error: sseError } = useObservatorySSE()

// ── Map ───────────────────────────────────────────────────────────────────────
const mapContainer = ref<HTMLElement | null>(null)
const { clickedFeature, hoveredTooltip, layerVisibility, setDemandLayer, setAssignmentsLayer, toggleLayer, onViewportChange, destroy } =
  useObservatoryMap(mapContainer)

// Last known viewport bbox — updated by map moveend/zoomend via onViewportChange.
// Fallback is CDMX until the map has loaded and emitted its first viewport event.
const currentBbox = ref('19.2,-99.4,19.6,-99.0')

// ── Slot selector ─────────────────────────────────────────────────────────────
const DAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

const dayOptions = DAY_NAMES.map((label, value) => ({ label, value }))
const hourOptions = Array.from({ length: 24 }, (_, h) => ({
  label: `${String(h).padStart(2, '0')}:00`,
  value: h,
}))

const { dia: initialDia, hora: initialHora } = getMXCurrentSlot()
const selectedDay  = ref<number>(initialDia)
const selectedHour = ref<number>(initialHora)

function goToNow() {
  const s = getMXCurrentSlot()
  selectedDay.value  = s.dia
  selectedHour.value = s.hora
}

// ── Demand data ───────────────────────────────────────────────────────────────
const demandPredictions = ref<DemandPrediction[]>([])
const loadingDemand = ref(false)

// In-memory cache keyed by `${hora}_${dia}_${bboxSnapped}`.
// bbox is already snapped to 1 decimal by the composable before emission.
const demandCache = new Map<string, DemandPrediction[]>()

async function fetchDemand(bbox: string) {
  if (!layerVisibility.value.demand) return

  const key = `${selectedHour.value}_${selectedDay.value}_${bbox}`
  if (demandCache.has(key)) {
    const cached = demandCache.get(key)!
    demandPredictions.value = cached
    await setDemandLayer(cached)
    return
  }
  loadingDemand.value = true
  try {
    const res = await demandApi.bySlot({
      dia_semana_num: selectedDay.value,
      hora_num:       selectedHour.value,
      bbox,
    })
    const data = Array.isArray(res) ? res : []
    demandCache.set(key, data)
    demandPredictions.value = data
    await setDemandLayer(data)
  } catch {
    demandPredictions.value = []
  } finally {
    loadingDemand.value = false
  }
}

// Re-fetch when slot changes — use the last known viewport bbox
watch([selectedDay, selectedHour], () => fetchDemand(currentBbox.value))

// Debounced viewport handler — registered once after map init via onViewportChange
let _viewportDebounce: ReturnType<typeof setTimeout> | null = null
onViewportChange((bbox) => {
  currentBbox.value = bbox
  if (_viewportDebounce) clearTimeout(_viewportDebounce)
  _viewportDebounce = setTimeout(() => fetchDemand(bbox), 350)
})

// ── Layer toggles → map ───────────────────────────────────────────────────────
function handleToggle(name: 'demand' | 'assignments' | 'routes') {
  const newVisible = !layerVisibility.value[name]
  toggleLayer(name, newVisible)
  // When demand layer is re-enabled, fetch the current viewport in case it
  // changed while the layer was off (data may be stale or missing).
  if (name === 'demand' && newVisible) fetchDemand(currentBbox.value)
}

// ── Positioning ───────────────────────────────────────────────────────────────
const radioKm      = ref(7.5)
const spreadFactor = ref(0.5)
const loadingOptimize = ref(false)
const optimizeResult  = ref<RecommendationResponse | null>(null)
const optimizeError   = ref<string | null>(null)

async function runOptimize() {
  loadingOptimize.value = true
  optimizeError.value   = null
  optimizeResult.value  = null
  try {
    optimizeResult.value = await recommendationsApi.generate({
      hora_num:       selectedHour.value,
      dia_semana_num: selectedDay.value,
      radio_km:       radioKm.value,
      spread_factor:  spreadFactor.value,
    })
  } catch (e) {
    optimizeError.value = e instanceof Error ? e.message : 'Error al optimizar'
  } finally {
    loadingOptimize.value = false
  }
}

// ── SSE → map assignments layer ───────────────────────────────────────────────
watch(activeAssignments, async (events) => {
  await setAssignmentsLayer(events)
}, { deep: true })

// ── SSE freshness indicator ───────────────────────────────────────────────────
const now = ref(Date.now())
let freshnessTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  freshnessTimer = setInterval(() => { now.value = Date.now() }, 10_000)
  fetchDemand(currentBbox.value)
})
onUnmounted(() => {
  if (freshnessTimer) clearInterval(freshnessTimer)
  if (_viewportDebounce) clearTimeout(_viewportDebounce)
  destroy()
})

const freshnessStatus = computed<'green' | 'yellow' | 'red'>(() => {
  if (!connected.value) return 'red'
  if (!lastEventAt.value) return 'yellow'
  const ageMs = now.value - new Date(lastEventAt.value).getTime()
  if (ageMs < 60_000)  return 'green'
  if (ageMs < 300_000) return 'yellow'
  return 'red'
})

const freshnessLabel = computed(() => {
  if (!connected.value) return 'Sin conexión'
  if (!lastEventAt.value) return 'En espera…'
  const ageS = Math.floor((now.value - new Date(lastEventAt.value).getTime()) / 1000)
  if (ageS < 60) return `Hace ${ageS}s`
  return `Hace ${Math.floor(ageS / 60)}m`
})

// ── KPI counts ────────────────────────────────────────────────────────────────
const kpiActiveAdjusters = computed(() => {
  const ids = new Set(activeAssignments.value.map((e) => e.adjuster?.id).filter(Boolean))
  return ids.size
})

const kpiOpenIncidents = computed(() => {
  const ids = new Set(activeAssignments.value.map((e) => e.incident.id))
  return ids.size
})

const kpiTotalKnown = computed(() => assignments.value.size)

// ── Side drawer ───────────────────────────────────────────────────────────────
const drawerVisible = computed(() => clickedFeature.value !== null)

function closeDrawer() {
  clickedFeature.value = null
}

const DEMAND_LABEL: Record<number, string> = { 0: 'Baja', 1: 'Media', 2: 'Alta' }
const DEMAND_SEVERITY: Record<number, string> = { 0: 'secondary', 1: 'warn', 2: 'danger' }

const STATUS_LABEL: Record<string, string> = {
  pending:     'Pendiente',
  assigned:    'Asignado',
  accepted:    'Aceptado',
  en_route:    'En camino',
  arrived:     'En sitio',
  in_progress: 'En atención',
  completed:   'Completado',
  cancelled:   'Cancelado',
}
</script>

<template>
  <div class="observatory-view">
    <!-- ── KPI bar ────────────────────────────────────────────────────── -->
    <div class="kpi-bar">
      <Card class="kpi-card">
        <template #content>
          <div class="kpi-inner">
            <span class="kpi-value">{{ kpiActiveAdjusters }}</span>
            <span class="kpi-label">Ajustadores activos</span>
          </div>
        </template>
      </Card>
      <Card class="kpi-card">
        <template #content>
          <div class="kpi-inner">
            <span class="kpi-value">{{ kpiOpenIncidents }}</span>
            <span class="kpi-label">Siniestros abiertos</span>
          </div>
        </template>
      </Card>
      <Card class="kpi-card">
        <template #content>
          <div class="kpi-inner">
            <span class="kpi-value">{{ kpiTotalKnown }}</span>
            <span class="kpi-label">Asignaciones conocidas</span>
          </div>
        </template>
      </Card>
      <Card class="kpi-card kpi-card--sse">
        <template #content>
          <div class="kpi-inner">
            <span class="sse-dot" :class="`sse-dot--${freshnessStatus}`" />
            <span class="kpi-value kpi-value--sm">SSE</span>
            <span class="kpi-label">{{ freshnessLabel }}</span>
          </div>
        </template>
      </Card>
    </div>

    <!-- ── Main area ─────────────────────────────────────────────────── -->
    <div class="observatory-body">
      <!-- Control panel -->
      <aside class="control-panel">
        <!-- Layer toggles -->
        <section class="panel-section">
          <h3 class="panel-title">Capas</h3>
          <div class="layer-toggles">
            <label class="toggle-row">
              <input
                type="checkbox"
                :checked="layerVisibility.demand"
                @change="handleToggle('demand')"
              />
              <span class="toggle-swatch toggle-swatch--demand" />
              Demanda
            </label>
            <label class="toggle-row">
              <input
                type="checkbox"
                :checked="layerVisibility.assignments"
                @change="handleToggle('assignments')"
              />
              <span class="toggle-swatch toggle-swatch--incidents" />
              Siniestros
            </label>
            <label class="toggle-row">
              <input
                type="checkbox"
                :checked="layerVisibility.routes"
                @change="handleToggle('routes')"
              />
              <span class="toggle-swatch toggle-swatch--routes" />
              Rutas
            </label>
          </div>
        </section>

        <!-- Slot selector -->
        <section class="panel-section">
          <h3 class="panel-title">Slot de demanda</h3>
          <div class="slot-controls">
            <Select
              v-model="selectedDay"
              :options="dayOptions"
              option-label="label"
              option-value="value"
              placeholder="Día"
              class="slot-select"
            />
            <Select
              v-model="selectedHour"
              :options="hourOptions"
              option-label="label"
              option-value="value"
              placeholder="Hora"
              class="slot-select"
            />
            <Button
              label="Ahora"
              icon="pi pi-clock"
              severity="secondary"
              size="small"
              class="slot-now-btn"
              @click="goToNow"
            />
          </div>
          <div v-if="loadingDemand" class="demand-loading">
            <ProgressSpinner style="width:20px;height:20px" />
            <span>Cargando…</span>
          </div>
          <div v-else-if="demandPredictions.length" class="demand-summary">
            {{ demandPredictions.length }} celdas H3 cargadas
          </div>
        </section>

        <!-- Positioning optimizer -->
        <section class="panel-section">
          <h3 class="panel-title">Posicionamiento</h3>
          <div class="optimizer-controls">
            <label class="slider-label">
              Radio (km): <strong>{{ radioKm }}</strong>
            </label>
            <Slider v-model="radioKm" :min="1" :max="30" :step="0.5" class="optimizer-slider" />

            <label class="slider-label">
              Dispersión: <strong>{{ spreadFactor }}</strong>
            </label>
            <Slider
              v-model="spreadFactor"
              :min="0"
              :max="1"
              :step="0.05"
              class="optimizer-slider"
            />

            <Button
              label="Optimizar"
              icon="pi pi-map-marker"
              :loading="loadingOptimize"
              class="optimize-btn"
              @click="runOptimize"
            />

            <div v-if="optimizeError" class="optimize-error">{{ optimizeError }}</div>

            <div v-if="optimizeResult" class="optimize-result">
              <span class="optimize-result-stat">
                {{ optimizeResult.adjusters_to_move }} / {{ optimizeResult.total_adjusters }}
                ajustadores a mover
              </span>
              <ul class="optimize-list">
                <li
                  v-for="rec in optimizeResult.recommendations"
                  :key="rec.adjuster_id"
                  class="optimize-item"
                >
                  <strong>{{ rec.adjuster_name }}</strong>
                  <span class="muted">→ {{ rec.recommended_hex.slice(0, 8) }}…</span>
                  <span class="optimize-gain">+{{ rec.demand_gain.toFixed(1) }}</span>
                </li>
              </ul>
            </div>
          </div>
        </section>

        <div v-if="sseError" class="sse-error">
          <span class="pi pi-exclamation-triangle" />
          {{ sseError }}
        </div>
      </aside>

      <!-- Map container + hover tooltip overlay -->
      <div class="map-wrapper">
        <div ref="mapContainer" class="map-container" />

        <!-- Hover tooltip — positioned over the canvas at Deck.gl pixel coords.
             Fades in/out in 150 ms. Appears 16px above the cursor so it never
             obscures the hovered marker. Shifts left when near the right edge. -->
        <Transition name="map-tooltip">
          <div
            v-if="hoveredTooltip"
            class="map-tooltip"
            :style="{
              left: `${hoveredTooltip.x}px`,
              top:  `${hoveredTooltip.y - 16}px`,
            }"
          >
            <!-- Status pill -->
            <div class="mtt-status-row">
              <span class="mtt-dot" :class="`mtt-dot--${hoveredTooltip.event.status}`" />
              <span class="mtt-status">{{ STATUS_LABEL[hoveredTooltip.event.status] ?? hoveredTooltip.event.status }}</span>
              <span class="mtt-id">#{{ hoveredTooltip.event.assignment_id }}</span>
            </div>
            <!-- Incident type + severity -->
            <div class="mtt-type">
              <span class="mtt-badge">{{ hoveredTooltip.event.incident.type.replace(/_/g, ' ') }}</span>
              <span class="mtt-severity" :data-lvl="hoveredTooltip.event.incident.severity">
                Sev {{ hoveredTooltip.event.incident.severity }}
              </span>
            </div>
            <!-- Address (truncated) -->
            <div v-if="hoveredTooltip.event.incident.address" class="mtt-address">
              {{ hoveredTooltip.event.incident.address }}
            </div>
            <!-- Distance + ETA -->
            <div v-if="hoveredTooltip.event.distance_km || hoveredTooltip.event.travel_time_minutes" class="mtt-meta">
              <span v-if="hoveredTooltip.event.distance_km">
                📍 {{ hoveredTooltip.event.distance_km.toFixed(1) }} km
              </span>
              <span v-if="hoveredTooltip.event.travel_time_minutes">
                ⏱ {{ hoveredTooltip.event.travel_time_minutes }} min
              </span>
            </div>
            <div class="mtt-hint">Clic para ver detalle</div>
          </div>
        </Transition>
      </div>
    </div>

    <!-- ── Side drawer ────────────────────────────────────────────────── -->
    <Drawer
      :visible="drawerVisible"
      position="right"
      :modal="false"
      header="Detalle"
      style="width: 360px"
      @update:visible="closeDrawer"
    >
      <template v-if="clickedFeature">
        <!-- Hexagon feature -->
        <div v-if="clickedFeature.type === 'hexagon'" class="drawer-content">
          <div class="drawer-row">
            <span class="drawer-label">Zona H3</span>
            <code class="drawer-value">{{ clickedFeature.h3Index }}</code>
          </div>
          <div class="drawer-row">
            <span class="drawer-label">Nivel de demanda</span>
            <Badge
              :value="DEMAND_LABEL[clickedFeature.demandLevel ?? 0] ?? clickedFeature.demandLevel"
              :severity="DEMAND_SEVERITY[clickedFeature.demandLevel ?? 0] ?? 'secondary'"
            />
          </div>
          <div class="drawer-row">
            <span class="drawer-label">Demanda absoluta</span>
            <span class="drawer-value">{{ clickedFeature.predAbs?.toFixed(2) }}</span>
          </div>
        </div>

        <!-- Assignment feature -->
        <div v-else-if="clickedFeature.type === 'assignment' && clickedFeature.assignmentEvent" class="drawer-content">
          <div class="drawer-row">
            <span class="drawer-label">Asignación</span>
            <span class="drawer-value">#{{ clickedFeature.assignmentEvent.assignment_id }}</span>
          </div>
          <div class="drawer-row">
            <span class="drawer-label">Ajustador</span>
            <span class="drawer-value">#{{ clickedFeature.assignmentEvent.adjuster?.id ?? '—' }}</span>
          </div>
          <div class="drawer-row">
            <span class="drawer-label">Siniestro</span>
            <span class="drawer-value">#{{ clickedFeature.assignmentEvent.incident.id }}</span>
          </div>
          <div class="drawer-row">
            <span class="drawer-label">Estado</span>
            <Badge :value="clickedFeature.assignmentEvent.status" severity="info" />
          </div>
          <div class="drawer-row">
            <span class="drawer-label">Tipo</span>
            <span class="drawer-value">{{ clickedFeature.assignmentEvent.incident.type }}</span>
          </div>
          <div v-if="clickedFeature.assignmentEvent.incident.address" class="drawer-row">
            <span class="drawer-label">Dirección</span>
            <span class="drawer-value drawer-value--wrap">{{ clickedFeature.assignmentEvent.incident.address }}</span>
          </div>
          <div v-if="clickedFeature.assignmentEvent.distance_km" class="drawer-row">
            <span class="drawer-label">Distancia</span>
            <span class="drawer-value">{{ clickedFeature.assignmentEvent.distance_km?.toFixed(1) }} km</span>
          </div>
          <div v-if="clickedFeature.assignmentEvent.travel_time_minutes" class="drawer-row">
            <span class="drawer-label">Tiempo estimado</span>
            <span class="drawer-value">{{ clickedFeature.assignmentEvent.travel_time_minutes }} min</span>
          </div>
          <div v-if="clickedFeature.assignmentEvent.route?.provider" class="drawer-row">
            <span class="drawer-label">Proveedor ruta</span>
            <span class="drawer-value muted">{{ clickedFeature.assignmentEvent.route.provider }}</span>
          </div>
        </div>
      </template>
    </Drawer>
  </div>
</template>

<style scoped>
/* ── Layout ─────────────────────────────────────────────────────────────────── */
.observatory-view {
  display: flex;
  flex-direction: column;
  /* AppLayout: 100vh - 56px topbar - 1.5rem padding-top - 1.5rem padding-bottom */
  height: calc(100vh - 56px - 3rem);
  gap: 0.75rem;
  overflow: hidden;
}

/* ── KPI bar ────────────────────────────────────────────────────────────────── */
.kpi-bar {
  display: flex;
  gap: 0.75rem;
  flex-shrink: 0;
}

.kpi-card {
  flex: 1;
}

.kpi-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
  padding: 0.25rem 0;
}

.kpi-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--p-surface-0);
  line-height: 1;
}

.kpi-value--sm {
  font-size: 1.1rem;
}

.kpi-label {
  font-size: 0.72rem;
  color: var(--p-surface-400);
  text-align: center;
}

.kpi-card--sse .kpi-inner {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.4rem;
}

.sse-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.sse-dot--green  { background: #22c55e; box-shadow: 0 0 6px #22c55e88; }
.sse-dot--yellow { background: #f59e0b; }
.sse-dot--red    { background: #ef4444; }

/* ── Body ───────────────────────────────────────────────────────────────────── */
.observatory-body {
  display: flex;
  gap: 0.75rem;
  flex: 1;
  min-height: 0;
}

/* ── Control panel ──────────────────────────────────────────────────────────── */
.control-panel {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0;
  background: var(--p-surface-900);
  border: 1px solid var(--p-surface-700);
  border-radius: 8px;
  overflow-y: auto;
}

.panel-section {
  padding: 0.9rem;
  border-bottom: 1px solid var(--p-surface-700);
}

.panel-section:last-child {
  border-bottom: none;
}

.panel-title {
  font-size: 0.72rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--p-surface-400);
  margin: 0 0 0.6rem;
}

/* Layer toggles */
.layer-toggles {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
  color: var(--p-surface-200);
  cursor: pointer;
  user-select: none;
}

.toggle-swatch {
  width: 12px;
  height: 12px;
  border-radius: 2px;
  flex-shrink: 0;
}

.toggle-swatch--demand   { background: #3b82f6; }
.toggle-swatch--incidents { background: #ef4444; }
.toggle-swatch--routes   { background: #6366f1; }

/* Slot selector */
.slot-controls {
  display: flex;
  flex-direction: column;
  gap: 0.45rem;
}

.slot-select {
  width: 100%;
}

.slot-now-btn {
  width: 100%;
}

.demand-loading {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: var(--p-surface-400);
}

.demand-summary {
  margin-top: 0.4rem;
  font-size: 0.78rem;
  color: var(--p-surface-400);
}

/* Optimizer */
.optimizer-controls {
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.slider-label {
  font-size: 0.8rem;
  color: var(--p-surface-300);
}

.optimizer-slider {
  width: 100%;
}

.optimize-btn {
  width: 100%;
}

.optimize-error {
  font-size: 0.78rem;
  color: var(--p-red-400);
}

.optimize-result {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.optimize-result-stat {
  font-size: 0.8rem;
  color: var(--p-surface-200);
}

.optimize-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.optimize-item {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.78rem;
  color: var(--p-surface-300);
}

.optimize-gain {
  margin-left: auto;
  color: #22c55e;
  font-weight: 600;
}

.sse-error {
  padding: 0.75rem 0.9rem;
  font-size: 0.78rem;
  color: var(--p-red-400);
  display: flex;
  gap: 0.4rem;
  align-items: flex-start;
}

/* ── Map wrapper + container ────────────────────────────────────────────────── */
.map-wrapper {
  flex: 1;
  min-width: 0;
  position: relative;   /* tooltip is absolutely positioned inside here */
}

.map-container {
  width: 100%;
  height: 100%;
  border-radius: 8px;
  overflow: hidden;
  background: var(--p-surface-800);
}

/* ── Hover tooltip ──────────────────────────────────────────────────────────── */
.map-tooltip {
  position: absolute;
  /* Shift left by 50% of its own width so it centres on the cursor.
     translateY(-100%) lifts the card fully above the anchor point. */
  transform: translate(-50%, -100%);
  pointer-events: none;   /* never intercepts mouse events — the canvas keeps them */
  z-index: 10;

  background: rgba(15, 15, 25, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 8px;
  backdrop-filter: blur(8px);
  padding: 0.55rem 0.75rem;
  min-width: 190px;
  max-width: 260px;

  display: flex;
  flex-direction: column;
  gap: 0.3rem;

  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.5);
}

/* Status row */
.mtt-status-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.mtt-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Status dot colours — mirror assignment status semantics */
.mtt-dot--pending,
.mtt-dot--assigned     { background: #f59e0b; }
.mtt-dot--accepted,
.mtt-dot--en_route     { background: #3b82f6; }
.mtt-dot--arrived,
.mtt-dot--in_progress  { background: #22c55e; }
.mtt-dot--completed    { background: #6b7280; }
.mtt-dot--cancelled    { background: #ef4444; }

.mtt-status {
  font-size: 0.78rem;
  font-weight: 600;
  color: #e5e7eb;
  flex: 1;
}

.mtt-id {
  font-size: 0.72rem;
  color: #6b7280;
  font-variant-numeric: tabular-nums;
}

/* Type + severity row */
.mtt-type {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.mtt-badge {
  font-size: 0.72rem;
  background: rgba(99, 102, 241, 0.25);
  color: #a5b4fc;
  border-radius: 4px;
  padding: 0.1rem 0.4rem;
  text-transform: capitalize;
  white-space: nowrap;
}

.mtt-severity {
  font-size: 0.7rem;
  color: #9ca3af;
}

/* Severity colour coding */
.mtt-severity[data-lvl="1"] { color: #6b7280; }
.mtt-severity[data-lvl="2"] { color: #84cc16; }
.mtt-severity[data-lvl="3"] { color: #f59e0b; }
.mtt-severity[data-lvl="4"] { color: #f97316; }
.mtt-severity[data-lvl="5"] { color: #ef4444; }

/* Address */
.mtt-address {
  font-size: 0.75rem;
  color: #9ca3af;
  overflow: hidden;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  line-height: 1.35;
}

/* Distance + ETA */
.mtt-meta {
  display: flex;
  gap: 0.7rem;
  font-size: 0.75rem;
  color: #d1d5db;
}

/* Hint footer */
.mtt-hint {
  font-size: 0.67rem;
  color: #4b5563;
  margin-top: 0.1rem;
  border-top: 1px solid rgba(255,255,255,0.05);
  padding-top: 0.25rem;
}

/* ── Tooltip fade transition ────────────────────────────────────────────────── */
.map-tooltip-enter-active,
.map-tooltip-leave-active {
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.map-tooltip-enter-from,
.map-tooltip-leave-to {
  opacity: 0;
  /* Slide up 6px on enter, slide down 6px on leave — subtle spring feel */
  transform: translate(-50%, calc(-100% + 6px));
}

.map-tooltip-enter-to,
.map-tooltip-leave-from {
  opacity: 1;
  transform: translate(-50%, -100%);
}

/* ── Drawer ─────────────────────────────────────────────────────────────────── */
.drawer-content {
  display: flex;
  flex-direction: column;
  gap: 0.9rem;
  padding: 0.25rem 0;
}

.drawer-row {
  display: flex;
  flex-direction: column;
  gap: 0.2rem;
}

.drawer-label {
  font-size: 0.72rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--p-surface-400);
}

.drawer-value {
  font-size: 0.9rem;
  color: var(--p-surface-100);
}

.drawer-value--wrap {
  white-space: pre-wrap;
  word-break: break-word;
}

.muted {
  color: var(--p-surface-500);
}
</style>
