<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Badge from 'primevue/badge'
import Select from 'primevue/select'
import Button from 'primevue/button'
import ProgressSpinner from 'primevue/progressspinner'
import EmptyState from '../components/EmptyState.vue'
import { demandApi } from '@slate/api-client'
import type { DemandPrediction, DemandSlot } from '@slate/types'

const slots = ref<DemandSlot[]>([])
const predictions = ref<DemandPrediction[]>([])
const loadingSlots = ref(true)
const loadingPredictions = ref(false)
const error = ref<string | null>(null)

const selectedDay = ref<number | null>(null)
const selectedHour = ref<number | null>(null)

// Ciudad de México como bbox por defecto
const DEFAULT_BBOX = '19.2,-99.4,19.6,-99.0'

const dayName = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']

const availableDays = computed(() => {
  const days = [...new Set(slots.value.map((s) => s.dia_semana_num))].sort()
  return days.map((d) => ({ label: dayName[d] ?? `Día ${d}`, value: d }))
})

const availableHours = computed(() => {
  if (selectedDay.value === null) return []
  const hours = slots.value
    .filter((s) => s.dia_semana_num === selectedDay.value)
    .map((s) => s.hora_num)
    .sort((a, b) => a - b)
  return hours.map((h) => ({
    label: `${String(h).padStart(2, '0')}:00`,
    value: h,
  }))
})

const demandLevelSeverity: Record<number, string> = {
  0: 'secondary',
  1: 'warn',
  2: 'danger',
}

const demandLevelLabel: Record<number, string> = {
  0: 'Baja',
  1: 'Media',
  2: 'Alta',
}

const maxPredAbs = computed(() =>
  Math.max(...predictions.value.map((p) => p.pred_abs), 1),
)

function barWidth(val: number): string {
  return `${Math.round((val / maxPredAbs.value) * 100)}%`
}

async function fetchPredictions() {
  if (selectedDay.value === null || selectedHour.value === null) return
  loadingPredictions.value = true
  error.value = null
  try {
    const res = await demandApi.bySlot({
      dia_semana_num: selectedDay.value,
      hora_num: selectedHour.value,
      bbox: DEFAULT_BBOX,
    })
    predictions.value = Array.isArray(res) ? res : []
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al cargar predicciones'
    predictions.value = []
  } finally {
    loadingPredictions.value = false
  }
}

watch(selectedDay, () => {
  selectedHour.value = null
  predictions.value = []
})

watch(selectedHour, (h) => {
  if (h !== null) fetchPredictions()
})

onMounted(async () => {
  try {
    const res = await demandApi.slots()
    slots.value = Array.isArray(res) ? res : []
    // Auto-select first available slot
    const first = slots.value[0]
    if (first) {
      selectedDay.value = first.dia_semana_num
      selectedHour.value = first.hora_num
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al cargar slots disponibles'
  } finally {
    loadingSlots.value = false
  }
})
</script>

<template>
  <div class="demand-view">
    <div class="view-header">
      <h1 class="view-title">Predicción de demanda</h1>
      <div class="view-filters">
        <div v-if="loadingSlots" class="loading-inline">
          <ProgressSpinner style="width:24px;height:24px" />
        </div>
        <template v-else>
          <Select
            v-model="selectedDay"
            :options="availableDays"
            option-label="label"
            option-value="value"
            placeholder="Día de la semana"
            :disabled="!availableDays.length"
            class="filter-select"
          />
          <Select
            v-model="selectedHour"
            :options="availableHours"
            option-label="label"
            option-value="value"
            placeholder="Hora"
            :disabled="selectedDay === null"
            class="filter-select"
          />
          <Button
            icon="pi pi-refresh"
            severity="secondary"
            :disabled="selectedHour === null"
            :loading="loadingPredictions"
            @click="fetchPredictions"
          />
        </template>
      </div>
    </div>

    <EmptyState v-if="error && !loadingPredictions" icon="pi-exclamation-circle" :error="error" />

    <Card v-else>
      <template #content>
        <div v-if="loadingPredictions" class="view-loading">
          <ProgressSpinner />
        </div>
        <DataTable
          v-else
          :value="predictions"
          :rows="20"
          paginator
          sort-field="pred_abs"
          :sort-order="-1"
        >
          <template #empty>
            <EmptyState
              icon="pi-chart-bar"
              title="Sin predicciones"
              :message="selectedHour === null
                ? 'Selecciona un día y hora para ver las predicciones.'
                : 'No hay datos para el slot seleccionado en esta zona.'"
            />
          </template>

          <Column field="h3_r8" header="Zona (H3)" style="width: 160px" />

          <Column header="Lat / Lon" style="width: 160px">
            <template #body="{ data }">
              {{ data.lat.toFixed(4) }}, {{ data.lon.toFixed(4) }}
            </template>
          </Column>

          <Column header="Nivel" style="width: 100px" sort-field="demand_level" sortable>
            <template #body="{ data }">
              <Badge
                :value="demandLevelLabel[data.demand_level] ?? data.demand_level"
                :severity="demandLevelSeverity[data.demand_level] ?? 'secondary'"
              />
            </template>
          </Column>

          <Column header="Demanda absoluta" sort-field="pred_abs" sortable>
            <template #body="{ data }">
              <div class="demand-bar-row">
                <div class="demand-bar-track">
                  <div
                    class="demand-bar-fill"
                    :class="`demand-bar--level-${data.demand_level}`"
                    :style="{ width: barWidth(data.pred_abs) }"
                  />
                </div>
                <span class="demand-value">{{ data.pred_abs.toFixed(2) }}</span>
              </div>
            </template>
          </Column>

          <Column header="Ratio" style="width: 90px" sort-field="pred_ratio" sortable>
            <template #body="{ data }">
              {{ data.pred_ratio.toFixed(3) }}
            </template>
          </Column>

          <Column header="Versión modelo" style="width: 130px">
            <template #body="{ data }">
              <span class="muted">{{ data.model_version }}</span>
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.demand-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.view-loading {
  display: flex;
  justify-content: center;
  padding: 4rem;
}

.view-header {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex-wrap: wrap;
}

.view-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
  flex: 1;
}

.view-filters {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.filter-select {
  width: 170px;
}

.loading-inline {
  display: flex;
  align-items: center;
  padding: 0.25rem;
}

.demand-bar-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.demand-bar-track {
  flex: 1;
  height: 8px;
  background: var(--p-surface-700);
  border-radius: 4px;
  overflow: hidden;
  min-width: 80px;
}

.demand-bar-fill {
  height: 100%;
  border-radius: 4px;
  background: var(--p-surface-500);
  transition: width 0.3s ease;
}

.demand-bar--level-1 { background: var(--p-yellow-400); }
.demand-bar--level-2 { background: var(--p-red-400); }

.demand-value {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-surface-200);
  min-width: 42px;
  text-align: right;
}

.muted {
  color: var(--p-surface-500);
  font-size: 0.8rem;
}
</style>
