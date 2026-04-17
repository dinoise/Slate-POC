<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import Tag from 'primevue/tag'
import Button from 'primevue/button'
import DataTable from 'primevue/datatable'
import Column from 'primevue/column'
import ProgressSpinner from 'primevue/progressspinner'
import { adjustersApi, assignmentsApi } from '@slate/api-client'
import type { Adjuster, Assignment } from '@slate/types'
import EmptyState from '../components/EmptyState.vue'

const route = useRoute()
const router = useRouter()

const adjuster = ref<Adjuster | null>(null)
const assignments = ref<Assignment[]>([])
const loading = ref(true)
const error = ref<string | null>(null)

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

const assignmentStatusSeverity: Record<string, string> = {
  assigned: 'warn',
  accepted: 'info',
  en_route: 'info',
  arrived: 'warn',
  completed: 'success',
  cancelled: 'danger',
}

const assignmentStatusLabel: Record<string, string> = {
  assigned: 'Asignado',
  accepted: 'Aceptado',
  en_route: 'En camino',
  arrived: 'Llegó',
  completed: 'Completado',
  cancelled: 'Cancelado',
}

onMounted(async () => {
  const id = Number(route.params.id)
  try {
    const [adj, asgns] = await Promise.all([
      adjustersApi.get(id),
      assignmentsApi.byAdjuster(id),
    ])
    adjuster.value = adj
    assignments.value = Array.isArray(asgns) ? asgns : []
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Error al cargar ajustador'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="adjuster-detail">
    <div class="detail-toolbar">
      <Button
        icon="pi pi-arrow-left"
        label="Ajustadores"
        severity="secondary"
        text
        @click="router.push('/adjusters')"
      />
    </div>

    <div v-if="loading" class="detail-loading">
      <ProgressSpinner />
    </div>

    <EmptyState v-else-if="error" icon="pi-exclamation-circle" :error="error" />

    <template v-else-if="adjuster">
      <div class="detail-header">
        <div class="adjuster-avatar">
          <span class="pi pi-user avatar-icon" />
        </div>
        <div>
          <h1 class="detail-title">{{ adjuster.name }}</h1>
          <p class="detail-subtitle">{{ adjuster.email }}</p>
        </div>
        <Badge
          :value="statusLabel[adjuster.status] ?? adjuster.status"
          :severity="statusSeverity[adjuster.status] ?? 'secondary'"
          class="status-badge"
        />
      </div>

      <div class="detail-grid">
        <!-- Info del ajustador -->
        <Card>
          <template #title>Perfil</template>
          <template #content>
            <dl class="info-list">
              <div class="info-row">
                <dt>Teléfono</dt>
                <dd>{{ adjuster.phone || '—' }}</dd>
              </div>
              <div class="info-row">
                <dt>Especialidades</dt>
                <dd>
                  <div class="tags-row">
                    <Tag
                      v-for="spec in adjuster.specializations"
                      :key="spec"
                      :value="spec"
                      severity="secondary"
                    />
                    <span v-if="!adjuster.specializations?.length" class="muted">Sin especialidades</span>
                  </div>
                </dd>
              </div>
              <div class="info-row">
                <dt>Última posición</dt>
                <dd>
                  <span v-if="adjuster.latitude && adjuster.longitude">
                    {{ adjuster.latitude.toFixed(5) }}, {{ adjuster.longitude.toFixed(5) }}
                  </span>
                  <span v-else class="muted">Sin ubicación registrada</span>
                </dd>
              </div>
              <div class="info-row">
                <dt>Registro</dt>
                <dd>{{ new Date(adjuster.created_at).toLocaleString('es-MX') }}</dd>
              </div>
            </dl>
          </template>
        </Card>

        <!-- Stats rápidas -->
        <Card>
          <template #title>Estadísticas</template>
          <template #content>
            <div class="stats-grid">
              <div class="stat">
                <span class="stat-value">{{ assignments.length }}</span>
                <span class="stat-label">Total asignaciones</span>
              </div>
              <div class="stat">
                <span class="stat-value">
                  {{ assignments.filter(a => a.status === 'completed').length }}
                </span>
                <span class="stat-label">Completadas</span>
              </div>
              <div class="stat">
                <span class="stat-value">
                  {{ assignments.filter(a => a.status === 'cancelled').length }}
                </span>
                <span class="stat-label">Canceladas</span>
              </div>
              <div class="stat">
                <span class="stat-value">
                  {{ assignments.find(a => ['assigned','accepted','en_route','arrived'].includes(a.status)) ? '1' : '0' }}
                </span>
                <span class="stat-label">En curso</span>
              </div>
            </div>
          </template>
        </Card>
      </div>

      <!-- Historial de asignaciones -->
      <Card>
        <template #title>Historial de asignaciones</template>
        <template #content>
          <DataTable
            :value="assignments"
            :rows="10"
            paginator
            row-hover
            @row-click="(e) => router.push(`/incidents/${e.data.incident_id}`)"
          >
            <template #empty>
              <EmptyState
                icon="pi-link"
                title="Sin asignaciones"
                message="Este ajustador no tiene asignaciones registradas."
              />
            </template>
            <Column field="id" header="ID" style="width: 70px" sortable />
            <Column field="incident_id" header="Incidente" style="width: 110px">
              <template #body="{ data }">
                <Button
                  :label="`#${data.incident_id}`"
                  severity="secondary"
                  size="small"
                  text
                  @click.stop="router.push(`/incidents/${data.incident_id}`)"
                />
              </template>
            </Column>
            <Column field="status" header="Estado" style="width: 130px" sortable>
              <template #body="{ data }">
                <Badge
                  :value="assignmentStatusLabel[data.status] ?? data.status"
                  :severity="assignmentStatusSeverity[data.status] ?? 'secondary'"
                />
              </template>
            </Column>
            <Column field="distance_km" header="Distancia" style="width: 110px">
              <template #body="{ data }">
                {{ data.distance_km != null ? `${data.distance_km} km` : '—' }}
              </template>
            </Column>
            <Column field="travel_time_minutes" header="Tiempo" style="width: 100px">
              <template #body="{ data }">
                {{ data.travel_time_minutes != null ? `${data.travel_time_minutes} min` : '—' }}
              </template>
            </Column>
            <Column header="Asignado" style="width: 160px" sortable sort-field="assigned_at">
              <template #body="{ data }">
                {{ new Date(data.assigned_at).toLocaleString('es-MX') }}
              </template>
            </Column>
            <Column header="Completado" style="width: 160px">
              <template #body="{ data }">
                {{ data.completed_at ? new Date(data.completed_at).toLocaleString('es-MX') : '—' }}
              </template>
            </Column>
          </DataTable>
        </template>
      </Card>
    </template>
  </div>
</template>

<style scoped>
.adjuster-detail {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.detail-loading {
  display: flex;
  justify-content: center;
  padding: 4rem;
}

.detail-toolbar {
  display: flex;
  align-items: center;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.adjuster-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: var(--p-surface-700);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.avatar-icon {
  font-size: 1.6rem;
  color: var(--p-surface-300);
}

.detail-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
}

.detail-subtitle {
  font-size: 0.9rem;
  color: var(--p-surface-400);
}

.status-badge {
  margin-left: auto;
}

.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .detail-grid { grid-template-columns: 1fr; }
}

.info-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.info-row {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.info-row dt {
  color: var(--p-surface-400);
  font-weight: 500;
}

.info-row dd {
  color: var(--p-surface-100);
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.muted {
  color: var(--p-surface-500);
  font-size: 0.85rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.75rem;
  background: var(--p-surface-800);
  border-radius: 8px;
}

.stat-value {
  font-size: 1.8rem;
  font-weight: 700;
  color: var(--p-surface-0);
}

.stat-label {
  font-size: 0.75rem;
  color: var(--p-surface-400);
  margin-top: 0.2rem;
  text-align: center;
}
</style>
