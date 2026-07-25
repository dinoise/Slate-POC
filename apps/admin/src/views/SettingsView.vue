<script setup lang="ts">
import { ref, onMounted } from 'vue'
import Card from 'primevue/card'
import Badge from 'primevue/badge'
import Button from 'primevue/button'
import Select from 'primevue/select'
import ProgressSpinner from 'primevue/progressspinner'
import { settingsApi, adjustersApi } from '@slate/api-client'
import type { RouteProvider } from '@slate/types'

const provider = ref<RouteProvider | null>(null)
const loadingSettings = ref(true)
const saving = ref(false)
const saveError = ref<string | null>(null)
const saveSuccess = ref(false)

const resettingStatus = ref(false)
const resetSuccess = ref(false)
const resetError = ref<string | null>(null)

const providerOptions: { label: string; value: RouteProvider }[] = [
  { label: 'OSRM', value: 'osrm' },
  { label: 'Valhalla', value: 'valhalla' },
  { label: 'Google Maps', value: 'google' },
]

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

async function resetAdjusterStatus() {
  resettingStatus.value = true
  resetError.value = null
  resetSuccess.value = false
  try {
    await adjustersApi.resetStatus()
    resetSuccess.value = true
    setTimeout(() => { resetSuccess.value = false }, 3000)
  } catch (e) {
    resetError.value = e instanceof Error ? e.message : 'Error al resetear estados'
  } finally {
    resettingStatus.value = false
  }
}

onMounted(async () => {
  try {
    const s = await settingsApi.get()
    provider.value = s.provider
  } catch {
    // settings endpoint may not be available
  } finally {
    loadingSettings.value = false
  }
})
</script>

<template>
  <div class="settings-view">
    <h1 class="view-title">Configuración</h1>

    <!-- Routing provider -->
    <Card>
      <template #title>Proveedor de rutas</template>
      <template #content>
        <div v-if="loadingSettings" class="loading-inline">
          <ProgressSpinner style="width:28px;height:28px" />
        </div>
        <div v-else class="settings-row">
          <div class="settings-field">
            <label class="settings-label">Proveedor activo</label>
            <div class="settings-control">
              <Select
                v-model="provider"
                :options="providerOptions"
                option-label="label"
                option-value="value"
                placeholder="Seleccionar proveedor"
                style="width: 200px"
              />
              <Badge v-if="provider" :value="provider.toUpperCase()" severity="info" />
            </div>
          </div>
          <div class="settings-actions">
            <span v-if="saveSuccess" class="feedback-success">
              <span class="pi pi-check" /> Guardado
            </span>
            <span v-if="saveError" class="feedback-error">{{ saveError }}</span>
            <Button
              label="Guardar cambio"
              icon="pi pi-save"
              :loading="saving"
              :disabled="!provider"
              @click="saveProvider"
            />
          </div>
        </div>
      </template>
    </Card>

    <!-- Adjuster management -->
    <Card>
      <template #title>Mantenimiento de ajustadores</template>
      <template #content>
        <div class="settings-row">
          <div class="settings-field">
            <label class="settings-label">Resetear estados</label>
            <p class="settings-description">
              Marca todos los ajustadores como <strong>disponible</strong>.
              Útil después de pruebas o al inicio de un turno.
            </p>
          </div>
          <div class="settings-actions">
            <span v-if="resetSuccess" class="feedback-success">
              <span class="pi pi-check" /> Estados reseteados
            </span>
            <span v-if="resetError" class="feedback-error">{{ resetError }}</span>
            <Button
              label="Resetear estados"
              icon="pi pi-refresh"
              severity="warn"
              :loading="resettingStatus"
              @click="resetAdjusterStatus"
            />
          </div>
        </div>
      </template>
    </Card>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.view-title {
  font-size: 1.4rem;
  font-weight: 700;
  color: var(--p-surface-0);
}

.loading-inline {
  display: flex;
  justify-content: center;
  padding: 1.5rem;
}

.settings-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.settings-field {
  flex: 1;
  min-width: 200px;
}

.settings-label {
  display: block;
  font-weight: 600;
  color: var(--p-surface-100);
  margin-bottom: 0.4rem;
  font-size: 0.9rem;
}

.settings-description {
  font-size: 0.85rem;
  color: var(--p-surface-400);
  margin: 0;
  line-height: 1.5;
}

.settings-control {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.settings-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

.feedback-success {
  color: var(--p-green-400);
  font-size: 0.875rem;
}

.feedback-error {
  color: var(--p-red-400);
  font-size: 0.875rem;
}
</style>
