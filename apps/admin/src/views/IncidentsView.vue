<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Badge from 'primevue/badge'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import EmptyState from '../components/EmptyState.vue'
import { useIncidentsStore } from '../stores/incidents'
import { formatMXDate } from '@slate/composables'

const router = useRouter()
const store = useIncidentsStore()

const filters = ref({
  global: { value: null, matchMode: 'contains' },
  status: { value: null, matchMode: 'equals' },
  severity: { value: null, matchMode: 'equals' },
})

const statusOptions = [
  { label: 'Abierto', value: 'open' },
  { label: 'En progreso', value: 'in_progress' },
  { label: 'Resuelto', value: 'resolved' },
]

const severityOptions = [
  { label: 'Crítico', value: 'critical' },
  { label: 'Alto', value: 'high' },
  { label: 'Medio', value: 'medium' },
  { label: 'Bajo', value: 'low' },
]

const severityMap: Record<string, string> = {
  critical: 'danger',
  high: 'warn',
  medium: 'info',
  low: 'secondary',
}

const statusMap: Record<string, string> = {
  open: 'danger',
  in_progress: 'warn',
  resolved: 'success',
}

function clearFilters() {
  filters.value.global.value = null
  filters.value.status.value = null
  filters.value.severity.value = null
}

onMounted(() => store.fetchAll())
</script>

<template>
  <div class="incidents-view">
    <div class="view-header">
      <h1 class="view-title">Incidentes</h1>
      <span class="view-subtitle">{{ store.total }} registros</span>
    </div>

    <DataTable
      :value="store.items"
      :loading="store.loading"
      v-model:filters="filters"
      filter-display="row"
      :global-filter-fields="['address', 'incident_type', 'description']"
      row-hover
      paginator
      :rows="20"
      :rows-per-page-options="[10, 20, 50]"
      @row-click="(e) => router.push(`/incidents/${e.data.id}`)"
      class="incidents-table"
    >
      <template #header>
        <div class="table-header">
          <InputText
            v-model="filters.global.value"
            placeholder="Buscar dirección, tipo..."
            class="search-input"
          />
          <Button
            label="Limpiar filtros"
            severity="secondary"
            size="small"
            icon="pi pi-filter-slash"
            @click="clearFilters"
          />
        </div>
      </template>

      <template #empty>
        <EmptyState
          icon="pi-exclamation-triangle"
          title="Sin incidentes"
          :message="store.error ?? 'No hay incidentes que coincidan con los filtros.'"
          :error="store.error"
        />
      </template>

      <Column field="id" header="ID" style="width: 70px" sortable />

      <Column field="incident_type" header="Tipo" sortable />

      <Column field="severity" header="Severidad" style="width: 130px" sortable>
        <template #body="{ data }">
          <Badge :value="data.severity" :severity="severityMap[data.severity] ?? 'info'" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="severityOptions"
            option-label="label"
            option-value="value"
            placeholder="Severidad"
            show-clear
            @change="filterCallback()"
          />
        </template>
      </Column>

      <Column field="status" header="Estado" style="width: 130px" sortable>
        <template #body="{ data }">
          <Badge :value="data.status" :severity="statusMap[data.status] ?? 'info'" />
        </template>
        <template #filter="{ filterModel, filterCallback }">
          <Select
            v-model="filterModel.value"
            :options="statusOptions"
            option-label="label"
            option-value="value"
            placeholder="Estado"
            show-clear
            @change="filterCallback()"
          />
        </template>
      </Column>

      <Column field="address" header="Dirección" />

      <Column header="Fecha" style="width: 160px" sortable sort-field="created_at">
        <template #body="{ data }">
          {{ formatMXDate(data.created_at) }}
        </template>
      </Column>

      <Column style="width: 60px">
        <template #body="{ data }">
          <Button
            icon="pi pi-eye"
            severity="secondary"
            size="small"
            rounded
            text
            @click.stop="router.push(`/incidents/${data.id}`)"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.incidents-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.view-header {
  display: flex;
  align-items: baseline;
  gap: 0.75rem;
}

.view-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
}

.view-subtitle {
  font-size: 0.85rem;
  color: var(--p-surface-400);
}

.table-header {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.search-input {
  width: 280px;
}

.table-empty {
  text-align: center;
  color: var(--p-surface-400);
  padding: 2rem;
}

.incidents-table :deep(tr) {
  cursor: pointer;
}
</style>
