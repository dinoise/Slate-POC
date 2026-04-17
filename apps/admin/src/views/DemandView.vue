<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Select from 'primevue/select'
import ProgressSpinner from 'primevue/progressspinner'
import EmptyState from '../components/EmptyState.vue'
import { demandApi } from '@slate/api-client'
import type { DemandPrediction } from '@slate/types'

const predictions = ref<DemandPrediction[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

const filterDay = ref<number | null>(null)
const filterHour = ref<number | null>(null)

const dayOptions = [
  { label: 'Todos los días', value: null },
  { label: 'Lunes', value: 0 },
  { label: 'Martes', value: 1 },
  { label: 'Miércoles', value: 2 },
  { label: 'Jueves', value: 3 },
  { label: 'Viernes', value: 4 },
  { label: 'Sábado', value: 5 },
  { label: 'Domingo', value: 6 },
]

const dayName = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

const hourOptions = [
  { label: 'Todas las horas', value: null },
  ...Array.from({ length: 24 }, (_, i) => ({
    label: `${String(i).padStart(2, '0')}:00`,
    value: i,
  })),
]

const filtered = computed(() => {
  let list = predictions.value
  if (filterDay.value !== null) list = list.filter((p) => p.day_of_week === filterDay.value)
  if (filterHour.value !== null) list = list.filter((p) => p.hour_of_day === filterHour.value)
  return list
})

const maxDemand = computed(() =>
  Math.max(...filtered.value.map((p) => p.predicted_demand), 1),
)

function demandBarWidth(val: number): string {
  return `${Math.round((val / maxDemand.value) * 100)}%`
}

function demandColor(val: number): string {
  const ratio = val / maxDemand.value
  if (ratio >= 0.75) return 'var(--p-red-400)'
  if (ratio >= 0.5) return 'var(--p-yellow-400)'
  if (ratio >= 0.25) return 'var(--p-blue-400)'
  return 'var(--p-surface-500)'
}

onMounted(async () => {
  try {
    const res = await demandApi.list()
    predictions.value = Array.isArray(res) ? res : []
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al cargar predicciones'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="demand-view">
    <div class="view-header">
      <h1 class="view-title">Predicción de demanda</h1>
      <div class="view-filters">
        <Select
          v-model="filterDay"
          :options="dayOptions"
          option-label="label"
          option-value="value"
          class="filter-select"
        />
        <Select
          v-model="filterHour"
          :options="hourOptions"
          option-label="label"
          option-value="value"
          class="filter-select"
        />
      </div>
    </div>

    <div v-if="loading" class="view-loading">
      <ProgressSpinner />
    </div>

    <EmptyState v-else-if="error" icon="pi-exclamation-circle" :error="error" />

    <template v-else>
      <Card>
        <template #content>
          <DataTable
            :value="filtered"
            :rows="20"
            paginator
            sort-field="predicted_demand"
            :sort-order="-1"
          >
            <template #empty>
              <EmptyState
                icon="pi-chart-bar"
                title="Sin predicciones"
                message="No hay datos de predicción de demanda para los filtros seleccionados."
              />
            </template>

            <Column header="Día" style="width: 80px" sort-field="day_of_week" sortable>
              <template #body="{ data }">
                {{ dayName[data.day_of_week] ?? data.day_of_week }}
              </template>
            </Column>

            <Column header="Hora" style="width: 80px" sort-field="hour_of_day" sortable>
              <template #body="{ data }">
                {{ String(data.hour_of_day).padStart(2, '0') }}:00
              </template>
            </Column>

            <Column field="h3_index" header="Zona (H3)" style="width: 160px" />

            <Column header="Lat / Lon" style="width: 160px">
              <template #body="{ data }">
                {{ data.latitude.toFixed(4) }}, {{ data.longitude.toFixed(4) }}
              </template>
            </Column>

            <Column header="Demanda prevista" sort-field="predicted_demand" sortable>
              <template #body="{ data }">
                <div class="demand-bar-row">
                  <div class="demand-bar-track">
                    <div
                      class="demand-bar-fill"
                      :style="{
                        width: demandBarWidth(data.predicted_demand),
                        background: demandColor(data.predicted_demand),
                      }"
                    />
                  </div>
                  <span class="demand-value">{{ data.predicted_demand.toFixed(2) }}</span>
                </div>
              </template>
            </Column>

            <Column header="Fecha" style="width: 140px" sort-field="prediction_date" sortable>
              <template #body="{ data }">
                {{ new Date(data.prediction_date).toLocaleDateString('es-MX') }}
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </template>
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
  gap: 0.75rem;
}

.filter-select {
  width: 180px;
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
  transition: width 0.3s ease;
}

.demand-value {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-surface-200);
  min-width: 40px;
  text-align: right;
}
</style>
