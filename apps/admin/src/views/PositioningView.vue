<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Badge from 'primevue/badge'
import Tag from 'primevue/tag'
import Select from 'primevue/select'
import ProgressSpinner from 'primevue/progressspinner'
import EmptyState from '../components/EmptyState.vue'
import { useAdjustersStore } from '../stores/adjusters'

const router = useRouter()
const adjustersStore = useAdjustersStore()

const filterStatus = ref<string | null>(null)
const filterLocation = ref<string | null>(null)

const statusOptions = [
  { label: 'Todos los estados', value: null },
  { label: 'Disponible', value: 'available' },
  { label: 'Ocupado', value: 'busy' },
  { label: 'Desconectado', value: 'offline' },
]

const locationOptions = [
  { label: 'Todos', value: null },
  { label: 'Con ubicación', value: 'with' },
  { label: 'Sin ubicación', value: 'without' },
]

const statusSeverity: Record<string, 'success' | 'warn' | 'secondary' | 'danger'> = {
  available: 'success',
  busy: 'warn',
  offline: 'secondary',
}

const statusLabel: Record<string, string> = {
  available: 'Disponible',
  busy: 'Ocupado',
  offline: 'Desconectado',
}

const filtered = computed(() => {
  let list = adjustersStore.items
  if (filterStatus.value) list = list.filter((a) => a.status === filterStatus.value)
  if (filterLocation.value === 'with') list = list.filter((a) => a.latitude && a.longitude)
  if (filterLocation.value === 'without') list = list.filter((a) => !a.latitude || !a.longitude)
  return list
})

const withLocationCount = computed(() =>
  adjustersStore.items.filter((a) => a.latitude && a.longitude).length,
)

onMounted(() => {
  adjustersStore.fetchAll()
})
</script>

<template>
  <div class="positioning-view">
    <div class="view-header">
      <h1 class="view-title">Posicionamiento de ajustadores</h1>
      <div class="view-filters">
        <Select
          v-model="filterStatus"
          :options="statusOptions"
          option-label="label"
          option-value="value"
          class="filter-select"
        />
        <Select
          v-model="filterLocation"
          :options="locationOptions"
          option-label="label"
          option-value="value"
          class="filter-select"
        />
      </div>
    </div>

    <!-- Summary cards -->
    <div class="summary-grid" v-if="!adjustersStore.loading">
      <Card class="summary-card">
        <template #content>
          <div class="summary-stat">
            <span class="pi pi-users summary-icon" />
            <div>
              <div class="summary-value">{{ adjustersStore.items.length }}</div>
              <div class="summary-label">Total ajustadores</div>
            </div>
          </div>
        </template>
      </Card>
      <Card class="summary-card">
        <template #content>
          <div class="summary-stat">
            <span class="pi pi-map-marker summary-icon summary-icon--success" />
            <div>
              <div class="summary-value">{{ withLocationCount }}</div>
              <div class="summary-label">Con ubicación activa</div>
            </div>
          </div>
        </template>
      </Card>
      <Card class="summary-card">
        <template #content>
          <div class="summary-stat">
            <span class="pi pi-circle-fill summary-icon summary-icon--success" />
            <div>
              <div class="summary-value">
                {{ adjustersStore.items.filter(a => a.status === 'available').length }}
              </div>
              <div class="summary-label">Disponibles ahora</div>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <div v-if="adjustersStore.loading" class="view-loading">
      <ProgressSpinner />
    </div>

    <Card v-else>
      <template #content>
        <DataTable
          :value="filtered"
          :rows="15"
          paginator
          row-hover
          @row-click="(e) => router.push(`/adjusters/${e.data.id}`)"
        >
          <template #empty>
            <EmptyState
              icon="pi-map"
              title="Sin ajustadores"
              :message="adjustersStore.error ?? 'No se encontraron ajustadores con los filtros seleccionados.'"
              :error="adjustersStore.error"
            />
          </template>

          <Column field="id" header="ID" style="width: 70px" sortable />

          <Column field="name" header="Nombre" sortable />

          <Column field="status" header="Estado" style="width: 140px" sortable>
            <template #body="{ data }">
              <Badge
                :value="statusLabel[data.status] ?? data.status"
                :severity="statusSeverity[data.status] ?? 'secondary'"
              />
            </template>
          </Column>

          <Column header="Especialidades" style="width: 200px">
            <template #body="{ data }">
              <div class="tags-row">
                <Tag
                  v-for="spec in (data.specializations ?? []).slice(0, 3)"
                  :key="spec"
                  :value="spec"
                  severity="secondary"
                  style="font-size: 0.7rem"
                />
                <span v-if="!data.specializations?.length" class="muted">—</span>
              </div>
            </template>
          </Column>

          <Column header="Última ubicación" style="min-width: 200px">
            <template #body="{ data }">
              <span v-if="data.latitude && data.longitude" class="location-cell">
                <span class="pi pi-map-marker location-icon" />
                {{ data.latitude.toFixed(4) }}, {{ data.longitude.toFixed(4) }}
              </span>
              <span v-else class="muted">Sin ubicación</span>
            </template>
          </Column>

          <Column header="Actualizado" style="width: 160px" sort-field="updated_at" sortable>
            <template #body="{ data }">
              {{ new Date(data.updated_at).toLocaleString('es-MX') }}
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.positioning-view {
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

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
}

.summary-stat {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.summary-icon {
  font-size: 1.6rem;
  color: var(--p-surface-400);
}

.summary-icon--success { color: var(--p-green-400); }

.summary-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--p-surface-0);
  line-height: 1;
}

.summary-label {
  font-size: 0.75rem;
  color: var(--p-surface-400);
  margin-top: 0.2rem;
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.location-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.85rem;
  color: var(--p-surface-200);
}

.location-icon {
  color: var(--p-green-400);
  font-size: 0.8rem;
}

.muted {
  color: var(--p-surface-500);
  font-size: 0.85rem;
}
</style>
