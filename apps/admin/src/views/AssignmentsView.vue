<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import Select from 'primevue/select'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import EmptyState from '../components/EmptyState.vue'
import { useAssignmentsStore } from '../stores/assignments'
import { useIncidentsStore } from '../stores/incidents'
import { useAdjustersStore } from '../stores/adjusters'
import { formatMXDate } from '@slate/composables'

const router = useRouter()
const assignmentsStore = useAssignmentsStore()
const incidentsStore = useIncidentsStore()
const adjustersStore = useAdjustersStore()

const filterStatus = ref<string | null>(null)
const filterText = ref('')

const statusOptions = [
  { label: 'Todos los estados', value: null },
  { label: 'Asignado', value: 'assigned' },
  { label: 'Aceptado', value: 'accepted' },
  { label: 'En camino', value: 'en_route' },
  { label: 'Llegó', value: 'arrived' },
  { label: 'Completado', value: 'completed' },
  { label: 'Cancelado', value: 'cancelled' },
]

const statusSeverity: Record<string, string> = {
  assigned: 'warn',
  accepted: 'info',
  en_route: 'info',
  arrived: 'warn',
  completed: 'success',
  cancelled: 'danger',
}

const statusLabel: Record<string, string> = {
  assigned: 'Asignado',
  accepted: 'Aceptado',
  en_route: 'En camino',
  arrived: 'Llegó',
  completed: 'Completado',
  cancelled: 'Cancelado',
}

// Build lookup maps for cross-referencing
const incidentMap = computed(() =>
  Object.fromEntries(incidentsStore.items.map((i) => [i.id, i])),
)
const adjusterMap = computed(() =>
  Object.fromEntries(adjustersStore.items.map((a) => [a.id, a])),
)

const filtered = computed(() => {
  let list = assignmentsStore.items
  if (filterStatus.value) {
    list = list.filter((a) => a.status === filterStatus.value)
  }
  if (filterText.value.trim()) {
    const q = filterText.value.trim().toLowerCase()
    list = list.filter((a) => {
      const incident = incidentMap.value[a.incident_id]
      const adjuster = adjusterMap.value[a.adjuster_id]
      return (
        String(a.id).includes(q) ||
        String(a.incident_id).includes(q) ||
        String(a.adjuster_id).includes(q) ||
        incident?.address?.toLowerCase().includes(q) ||
        `${adjuster?.first_name ?? ''} ${adjuster?.last_name ?? ''}`.toLowerCase().includes(q)
      )
    })
  }
  return list
})

function adjusterName(id: number): string {
  const a = adjusterMap.value[id]
  return a ? `${a.first_name} ${a.last_name}` : `#${id}`
}

onMounted(() => {
  assignmentsStore.fetchAll()
  incidentsStore.fetchAll()
  adjustersStore.fetchAll()
})
</script>

<template>
  <div class="assignments-view">
    <div class="view-header">
      <h1 class="view-title">Asignaciones</h1>
      <div class="view-filters">
        <InputText
          v-model="filterText"
          placeholder="Buscar por ID, dirección, ajustador…"
          class="filter-search"
        />
        <Select
          v-model="filterStatus"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          class="filter-select"
        />
      </div>
    </div>

    <div v-if="assignmentsStore.loading" class="view-loading">
      <ProgressSpinner />
    </div>

    <DataTable
      v-else
      :value="filtered"
      :rows="15"
      paginator
      row-hover
      sort-field="assigned_at"
      :sort-order="-1"
    >
      <template #empty>
        <EmptyState
          icon="pi-link"
          title="Sin asignaciones"
          :message="assignmentsStore.error ?? 'No hay asignaciones registradas aún.'"
          :error="assignmentsStore.error"
        />
      </template>

      <Column field="id" header="ID" style="width: 70px" sortable />

      <Column field="incident_id" header="Incidente" style="width: 130px" sortable>
        <template #body="{ data }">
          <Button
            :label="`#${data.incident_id}`"
            severity="secondary"
            size="small"
            text
            @click="router.push(`/incidents/${data.incident_id}`)"
          />
        </template>
      </Column>

      <Column header="Dirección" style="min-width: 180px">
        <template #body="{ data }">
          <span class="address-cell">
            {{ incidentMap[data.incident_id]?.address ?? '—' }}
          </span>
        </template>
      </Column>

      <Column field="adjuster_id" header="Ajustador" style="width: 160px" sortable>
        <template #body="{ data }">
          <Button
            :label="adjusterName(data.adjuster_id)"
            severity="secondary"
            size="small"
            text
            @click="router.push(`/adjusters/${data.adjuster_id}`)"
          />
        </template>
      </Column>

      <Column field="status" header="Estado" style="width: 140px" sortable>
        <template #body="{ data }">
          <Badge
            :value="statusLabel[data.status] ?? data.status"
            :severity="statusSeverity[data.status] ?? 'secondary'"
          />
        </template>
      </Column>

      <Column field="distance_km" header="Distancia" style="width: 110px" sortable>
        <template #body="{ data }">
          {{ data.distance_km != null ? `${data.distance_km} km` : '—' }}
        </template>
      </Column>

      <Column field="travel_time_minutes" header="Tiempo" style="width: 100px" sortable>
        <template #body="{ data }">
          {{ data.travel_time_minutes != null ? `${data.travel_time_minutes} min` : '—' }}
        </template>
      </Column>

      <Column header="Asignado" style="width: 160px" sortable sort-field="assigned_at">
        <template #body="{ data }">
          {{ formatMXDate(data.assigned_at) }}
        </template>
      </Column>

      <Column header="Completado" style="width: 160px">
        <template #body="{ data }">
          {{ formatMXDate(data.completed_at) }}
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.assignments-view {
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
  flex-wrap: wrap;
}

.filter-search {
  width: 280px;
}

.filter-select {
  width: 200px;
}

.address-cell {
  font-size: 0.85rem;
  color: var(--p-surface-300);
}
</style>
