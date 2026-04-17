<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import Select from 'primevue/select'
import ProgressSpinner from 'primevue/progressspinner'
import { settingsApi } from '@slate/api-client'
import type { RouteProvider } from '@slate/types'
import { useAssignmentsStore } from '../stores/assignments'

const assignmentsStore = useAssignmentsStore()

const provider = ref<RouteProvider | null>(null)
const loadingSettings = ref(true)
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveSuccess = ref(false)

const providerOptions: { label: string; value: RouteProvider; description: string }[] = [
  { label: 'OSRM', value: 'osrm', description: 'Open Source Routing Machine — rápido, auto-hospedado' },
  { label: 'Valhalla', value: 'valhalla', description: 'Routing flexible con soporte multimodal' },
  { label: 'Google Maps', value: 'google', description: 'Alta precisión, requiere API key de Google' },
]

const completedAssignments = computed(() =>
  assignmentsStore.items.filter((a) => a.status === 'completed'),
)

const avgDistance = computed(() => {
  const withDist = completedAssignments.value.filter((a) => a.distance_km != null)
  if (!withDist.length) return null
  const sum = withDist.reduce((acc, a) => acc + (a.distance_km ?? 0), 0)
  return (sum / withDist.length).toFixed(1)
})

const avgTime = computed(() => {
  const withTime = completedAssignments.value.filter((a) => a.travel_time_minutes != null)
  if (!withTime.length) return null
  const sum = withTime.reduce((acc, a) => acc + (a.travel_time_minutes ?? 0), 0)
  return Math.round(sum / withTime.length)
})

async function saveProvider() {
  if (!provider.value) return
  saving.value = true
  saveError.value = null
  saveSuccess.value = false
  try {
    await settingsApi.update(provider.value)
    saveSuccess.value = true
    setTimeout(() => { saveSuccess.value = false }, 3000)
  } catch (e) {
    saveError.value = e instanceof Error ? e.message : 'Error al guardar configuración'
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    const s = await settingsApi.get()
    provider.value = s.provider
  } catch {
    // settings endpoint may not be available — keep null
  } finally {
    loadingSettings.value = false
  }
  assignmentsStore.fetchAll()
})
</script>

<template>
  <div class="optimization-view">
    <h1 class="view-title">Optimización de rutas</h1>

    <div class="opt-grid">
      <!-- Proveedor de rutas -->
      <Card>
        <template #title>Proveedor de enrutamiento</template>
        <template #content>
          <div v-if="loadingSettings" class="loading-inline">
            <ProgressSpinner style="width:28px;height:28px" />
          </div>
          <div v-else class="provider-form">
            <div class="provider-options">
              <div
                v-for="opt in providerOptions"
                :key="opt.value"
                class="provider-option"
                :class="{ 'provider-option--active': provider === opt.value }"
                @click="provider = opt.value"
              >
                <div class="provider-radio">
                  <span
                    class="pi"
                    :class="provider === opt.value ? 'pi-check-circle' : 'pi-circle'"
                  />
                </div>
                <div>
                  <div class="provider-name">{{ opt.label }}</div>
                  <div class="provider-desc">{{ opt.description }}</div>
                </div>
              </div>
            </div>

            <div class="provider-actions">
              <span v-if="saveSuccess" class="save-success">
                <span class="pi pi-check" /> Guardado
              </span>
              <span v-if="saveError" class="save-error">{{ saveError }}</span>
              <Button
                label="Guardar"
                icon="pi pi-save"
                :loading="saving"
                :disabled="!provider"
                @click="saveProvider"
              />
            </div>
          </div>
        </template>
      </Card>

      <!-- Estadísticas de optimización -->
      <Card>
        <template #title>Métricas de despacho</template>
        <template #content>
          <div v-if="assignmentsStore.loading" class="loading-inline">
            <ProgressSpinner style="width:28px;height:28px" />
          </div>
          <div v-else class="stats-grid">
            <div class="stat">
              <span class="stat-value">{{ completedAssignments.length }}</span>
              <span class="stat-label">Asignaciones completadas</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{ avgDistance != null ? `${avgDistance} km` : '—' }}</span>
              <span class="stat-label">Distancia promedio</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{ avgTime != null ? `${avgTime} min` : '—' }}</span>
              <span class="stat-label">Tiempo promedio de viaje</span>
            </div>
            <div class="stat">
              <span class="stat-value">
                {{ assignmentsStore.items.filter(a => a.status === 'cancelled').length }}
              </span>
              <span class="stat-label">Canceladas</span>
            </div>
          </div>
        </template>
      </Card>
    </div>

    <!-- Proveedor activo -->
    <Card v-if="provider">
      <template #content>
        <div class="active-provider">
          <span class="pi pi-map-marker active-icon" />
          <div>
            <div class="active-label">Proveedor activo</div>
            <div class="active-value">
              <Badge :value="provider.toUpperCase()" severity="info" />
            </div>
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.optimization-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.view-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
}

.opt-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
}

@media (max-width: 768px) {
  .opt-grid { grid-template-columns: 1fr; }
}

.loading-inline {
  display: flex;
  justify-content: center;
  padding: 1.5rem;
}

.provider-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.provider-options {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.provider-option {
  display: flex;
  align-items: flex-start;
  gap: 0.75rem;
  padding: 0.75rem;
  border: 1px solid var(--p-surface-700);
  border-radius: 8px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.provider-option:hover {
  border-color: var(--p-surface-500);
}

.provider-option--active {
  border-color: var(--p-primary-400);
  background: color-mix(in srgb, var(--p-primary-400) 8%, transparent);
}

.provider-radio .pi {
  font-size: 1.1rem;
  color: var(--p-surface-500);
  margin-top: 1px;
}

.provider-option--active .provider-radio .pi {
  color: var(--p-primary-400);
}

.provider-name {
  font-weight: 600;
  color: var(--p-surface-100);
  font-size: 0.9rem;
}

.provider-desc {
  font-size: 0.8rem;
  color: var(--p-surface-400);
  margin-top: 0.15rem;
}

.provider-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 0.75rem;
}

.save-success {
  color: var(--p-green-400);
  font-size: 0.875rem;
}

.save-error {
  color: var(--p-red-400);
  font-size: 0.875rem;
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
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--p-surface-0);
}

.stat-label {
  font-size: 0.75rem;
  color: var(--p-surface-400);
  margin-top: 0.2rem;
  text-align: center;
}

.active-provider {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.active-icon {
  font-size: 1.8rem;
  color: var(--p-blue-400);
  opacity: 0.8;
}

.active-label {
  font-size: 0.8rem;
  color: var(--p-surface-400);
  margin-bottom: 0.3rem;
}
</style>
