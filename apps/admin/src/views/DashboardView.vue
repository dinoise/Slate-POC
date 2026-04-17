<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import Card from 'primevue/card'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import Badge from 'primevue/badge'
import ProgressSpinner from 'primevue/progressspinner'
import EmptyState from '../components/EmptyState.vue'
import { useIncidentsStore } from '../stores/incidents'
import { useAdjustersStore } from '../stores/adjusters'
import { useAssignmentsStore } from '../stores/assignments'

const router = useRouter()
const incidentsStore = useIncidentsStore()
const adjustersStore = useAdjustersStore()
const assignmentsStore = useAssignmentsStore()

const activeIncidents = computed(() =>
  incidentsStore.items.filter((i) => i.status !== 'resolved').length,
)
const availableAdjusters = computed(() =>
  adjustersStore.items.filter((a) => a.status === 'available').length,
)
const pendingAssignments = computed(() =>
  assignmentsStore.items.filter((a) => a.status === 'assigned').length,
)

const recentIncidents = computed(() =>
  [...incidentsStore.items]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 8),
)

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

onMounted(() => {
  incidentsStore.fetchAll()
  adjustersStore.fetchAll()
  assignmentsStore.fetchAll()
})
</script>

<template>
  <div class="dashboard">
    <h1 class="dashboard-title">Dashboard</h1>

    <!-- Métricas -->
    <div class="metrics-grid">
      <Card class="metric-card">
        <template #content>
          <div class="metric">
            <span class="pi pi-exclamation-triangle metric-icon metric-icon--danger" />
            <div>
              <div class="metric-value">
                <ProgressSpinner v-if="incidentsStore.loading" style="width:24px;height:24px" />
                <span v-else>{{ activeIncidents }}</span>
              </div>
              <div class="metric-label">Incidentes activos</div>
            </div>
          </div>
        </template>
      </Card>

      <Card class="metric-card">
        <template #content>
          <div class="metric">
            <span class="pi pi-users metric-icon metric-icon--success" />
            <div>
              <div class="metric-value">
                <ProgressSpinner v-if="adjustersStore.loading" style="width:24px;height:24px" />
                <span v-else>{{ availableAdjusters }}</span>
              </div>
              <div class="metric-label">Ajustadores disponibles</div>
            </div>
          </div>
        </template>
      </Card>

      <Card class="metric-card">
        <template #content>
          <div class="metric">
            <span class="pi pi-link metric-icon metric-icon--warn" />
            <div>
              <div class="metric-value">
                <ProgressSpinner v-if="assignmentsStore.loading" style="width:24px;height:24px" />
                <span v-else>{{ pendingAssignments }}</span>
              </div>
              <div class="metric-label">Asignaciones pendientes</div>
            </div>
          </div>
        </template>
      </Card>

      <Card class="metric-card">
        <template #content>
          <div class="metric">
            <span class="pi pi-database metric-icon metric-icon--info" />
            <div>
              <div class="metric-value">{{ incidentsStore.total }}</div>
              <div class="metric-label">Total incidentes</div>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <!-- Incidentes recientes -->
    <Card class="recent-card">
      <template #title>Incidentes recientes</template>
      <template #content>
        <DataTable
          :value="recentIncidents"
          :loading="incidentsStore.loading"
          row-hover
          @row-click="(e) => router.push(`/incidents/${e.data.id}`)"
          class="recent-table"
        >
          <Column field="id" header="ID" style="width: 70px" />
          <Column field="incident_type" header="Tipo" />
          <Column header="Severidad" style="width: 120px">
            <template #body="{ data }">
              <Badge :value="data.severity" :severity="severityMap[data.severity] ?? 'info'" />
            </template>
          </Column>
          <Column header="Estado" style="width: 120px">
            <template #body="{ data }">
              <Badge :value="data.status" :severity="statusMap[data.status] ?? 'info'" />
            </template>
          </Column>
          <Column field="address" header="Dirección" />
          <Column header="Fecha" style="width: 160px">
            <template #body="{ data }">
              {{ new Date(data.created_at).toLocaleString('es-MX') }}
            </template>
          </Column>
          <template #empty>
            <EmptyState
              icon="pi-exclamation-triangle"
              title="Sin incidentes"
              :message="incidentsStore.error ?? 'No hay incidentes registrados aún.'"
              :error="incidentsStore.error"
            />
          </template>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.dashboard-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
  margin-bottom: 1.5rem;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.metric {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.metric-icon {
  font-size: 2rem;
  opacity: 0.85;
}
.metric-icon--danger  { color: var(--p-red-400); }
.metric-icon--success { color: var(--p-green-400); }
.metric-icon--warn    { color: var(--p-yellow-400); }
.metric-icon--info    { color: var(--p-blue-400); }

.metric-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--p-surface-0);
  line-height: 1;
}

.metric-label {
  font-size: 0.8rem;
  color: var(--p-surface-400);
  margin-top: 0.25rem;
}

.recent-card {
  margin-top: 0.5rem;
}

.recent-table :deep(tr) {
  cursor: pointer;
}
</style>
