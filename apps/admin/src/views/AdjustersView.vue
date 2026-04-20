<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useToast } from 'primevue/usetoast'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Badge from 'primevue/badge'
import Tag from 'primevue/tag'
import InputText from 'primevue/inputtext'
import Select from 'primevue/select'
import Button from 'primevue/button'
import EmptyState from '../components/EmptyState.vue'
import AdjusterFormDialog from '../components/AdjusterFormDialog.vue'
import { useAdjustersStore } from '../stores/adjusters'

const router = useRouter()
const toast = useToast()
const store = useAdjustersStore()

const showCreateDialog = ref(false)

function onAdjusterCreated() {
  toast.add({ severity: 'success', summary: 'Ajustador creado', life: 3000 })
}

const filters = ref({
  global: { value: null, matchMode: 'contains' },
  status: { value: null, matchMode: 'equals' },
})

const statusOptions = [
  { label: 'Disponible', value: 'available' },
  { label: 'Ocupado', value: 'busy' },
  { label: 'Desconectado', value: 'offline' },
]

const statusSeverity: Record<string, 'success' | 'warn' | 'secondary'> = {
  available: 'success',
  busy: 'warn',
  offline: 'secondary',
}

const statusLabel: Record<string, string> = {
  available: 'Disponible',
  busy: 'Ocupado',
  offline: 'Desconectado',
}

function clearFilters() {
  filters.value.global.value = null
  filters.value.status.value = null
}

onMounted(() => store.fetchAll())
</script>

<template>
  <div class="adjusters-view">
    <div class="view-header">
      <h1 class="view-title">Ajustadores</h1>
      <span class="view-subtitle">{{ store.total }} registros</span>
      <Button
        label="Nuevo ajustador"
        icon="pi pi-plus"
        size="small"
        class="ml-auto"
        @click="showCreateDialog = true"
      />
    </div>

    <AdjusterFormDialog
      v-model="showCreateDialog"
      @created="onAdjusterCreated"
    />

    <DataTable
      :value="store.items"
      :loading="store.loading"
      v-model:filters="filters"
      filter-display="row"
      :global-filter-fields="['name', 'email', 'phone']"
      row-hover
      paginator
      :rows="20"
      :rows-per-page-options="[10, 20, 50]"
      @row-click="(e) => router.push(`/adjusters/${e.data.id}`)"
      class="adjusters-table"
    >
      <template #header>
        <div class="table-header">
          <InputText
            v-model="filters.global.value"
            placeholder="Buscar nombre, email..."
            class="search-input"
          />
          <Button
            label="Limpiar"
            severity="secondary"
            size="small"
            icon="pi pi-filter-slash"
            @click="clearFilters"
          />
        </div>
      </template>

      <template #empty>
        <EmptyState
          icon="pi-users"
          title="Sin ajustadores"
          :message="store.error ?? 'No hay ajustadores registrados.'"
          :error="store.error"
        />
      </template>

      <Column field="id" header="ID" style="width: 70px" sortable />

      <Column field="name" header="Nombre" sortable />

      <Column field="email" header="Email" />

      <Column field="phone" header="Teléfono" style="width: 140px" />

      <Column field="status" header="Estado" style="width: 150px" sortable>
        <template #body="{ data }">
          <Badge
            :value="statusLabel[data.status] ?? data.status"
            :severity="statusSeverity[data.status] ?? 'secondary'"
          />
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

      <Column header="Especialidades">
        <template #body="{ data }">
          <div class="tags-row">
            <Tag
              v-for="spec in data.specializations"
              :key="spec"
              :value="spec"
              severity="secondary"
              class="spec-tag"
            />
            <span v-if="!data.specializations?.length" class="no-specs">—</span>
          </div>
        </template>
      </Column>

      <Column header="Ubicación" style="width: 120px">
        <template #body="{ data }">
          <span v-if="data.latitude && data.longitude" class="location-badge">
            <span class="pi pi-map-marker" />
            Activa
          </span>
          <span v-else class="no-specs">Sin ubicación</span>
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
            @click.stop="router.push(`/adjusters/${data.id}`)"
          />
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<style scoped>
.adjusters-view {
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

.adjusters-table :deep(tr) {
  cursor: pointer;
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.spec-tag {
  font-size: 0.7rem;
}

.no-specs {
  color: var(--p-surface-500);
  font-size: 0.85rem;
}

.location-badge {
  display: flex;
  align-items: center;
  gap: 0.3rem;
  font-size: 0.8rem;
  color: var(--p-green-400);
}
</style>
