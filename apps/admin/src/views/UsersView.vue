<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Badge from 'primevue/badge'
import InputText from 'primevue/inputtext'
import ProgressSpinner from 'primevue/progressspinner'
import EmptyState from '../components/EmptyState.vue'
import { usersApi } from '@slate/api-client'
import type { User } from '@slate/types'

const users = ref<User[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const filterText = ref('')

const roleSeverity: Record<string, string> = {
  admin: 'danger',
  operator: 'warn',
  viewer: 'secondary',
}

const filtered = computed(() => {
  if (!filterText.value.trim()) return users.value
  const q = filterText.value.trim().toLowerCase()
  return users.value.filter(
    (u) =>
      u.name.toLowerCase().includes(q) ||
      u.email.toLowerCase().includes(q) ||
      u.role.toLowerCase().includes(q),
  )
})

onMounted(async () => {
  try {
    const res = await usersApi.list()
    users.value = Array.isArray(res) ? res : []
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al cargar usuarios'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="users-view">
    <div class="view-header">
      <h1 class="view-title">Usuarios</h1>
      <InputText
        v-model="filterText"
        placeholder="Buscar por nombre, email o rol…"
        class="filter-search"
      />
    </div>

    <div v-if="loading" class="view-loading">
      <ProgressSpinner />
    </div>

    <EmptyState v-else-if="error" icon="pi-exclamation-circle" :error="error" />

    <Card v-else>
      <template #content>
        <DataTable :value="filtered" :rows="15" paginator row-hover sort-field="name" :sort-order="1">
          <template #empty>
            <EmptyState
              icon="pi-users"
              title="Sin usuarios"
              message="No se encontraron usuarios con los filtros seleccionados."
            />
          </template>

          <Column field="id" header="ID" style="width: 70px" sortable />

          <Column field="name" header="Nombre" sortable />

          <Column field="email" header="Email" sortable />

          <Column field="role" header="Rol" style="width: 130px" sortable>
            <template #body="{ data }">
              <Badge
                :value="data.role"
                :severity="roleSeverity[data.role] ?? 'secondary'"
              />
            </template>
          </Column>

          <Column header="Registro" style="width: 160px" sort-field="created_at" sortable>
            <template #body="{ data }">
              {{ new Date(data.created_at).toLocaleString('es-MX') }}
            </template>
          </Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.users-view {
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

.filter-search {
  width: 280px;
}
</style>
