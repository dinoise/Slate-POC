<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import Dialog from 'primevue/dialog'
import InputText from 'primevue/inputtext'
import InputNumber from 'primevue/inputnumber'
import InputChips from 'primevue/inputchips'
import Button from 'primevue/button'
import Message from 'primevue/message'
import Divider from 'primevue/divider'
import LocationPicker from './LocationPicker.vue'
import { useAdjustersStore } from '../stores/adjusters'
import type { AdjusterCreate } from '@slate/types'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  created: []
}>()

const store = useAdjustersStore()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// ── Form state ────────────────────────────────────────────────────────────────

const defaultForm = (): AdjusterCreate => ({
  external_id: '',
  first_name: '',
  last_name: '',
  email: '',
  phone: '',
  home_latitude: 0,
  home_longitude: 0,
  skills: [],
  max_cases_per_day: 5,
})

const form = ref<AdjusterCreate>(defaultForm())
const errors = ref<Partial<Record<keyof AdjusterCreate | 'location', string>>>({})
const submitting = ref(false)
const apiError = ref('')

watch(visible, (v) => {
  if (v) {
    form.value = defaultForm()
    errors.value = {}
    apiError.value = ''
  }
})

// ── Validation ────────────────────────────────────────────────────────────────

function validate(): boolean {
  const e: typeof errors.value = {}
  if (!form.value.external_id.trim()) e.external_id = 'Requerido'
  if (!form.value.first_name.trim()) e.first_name = 'Requerido'
  if (!form.value.last_name.trim()) e.last_name = 'Requerido'
  if (!form.value.email.trim()) {
    e.email = 'Requerido'
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.value.email)) {
    e.email = 'Email inválido'
  }
  if (!form.value.home_latitude || !form.value.home_longitude) {
    e.location = 'Selecciona una ubicación en el mapa'
  }
  errors.value = e
  return Object.keys(e).length === 0
}

// ── Submit ────────────────────────────────────────────────────────────────────

async function submit() {
  if (!validate()) return
  submitting.value = true
  apiError.value = ''
  try {
    const payload: AdjusterCreate = {
      ...form.value,
      phone: form.value.phone?.trim() || undefined,
    }
    await store.create(payload)
    emit('created')
    visible.value = false
  } catch (e) {
    apiError.value = e instanceof Error ? e.message : 'Error al crear ajustador'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <Dialog
    v-model:visible="visible"
    header="Nuevo ajustador"
    modal
    :style="{ width: '680px', maxWidth: '95vw' }"
    :draggable="false"
  >
    <div class="form-body">
      <!-- Información básica — en contenedor scrolleable -->
      <div class="fields-scroll">
        <section class="form-section">
          <h3 class="section-title">Información básica</h3>

          <div class="field-row">
            <div class="field">
              <label>Nombre *</label>
              <InputText
                v-model="form.first_name"
                placeholder="Juan"
                :invalid="!!errors.first_name"
                fluid
              />
              <small v-if="errors.first_name" class="field-error">{{ errors.first_name }}</small>
            </div>
            <div class="field">
              <label>Apellido *</label>
              <InputText
                v-model="form.last_name"
                placeholder="Pérez"
                :invalid="!!errors.last_name"
                fluid
              />
              <small v-if="errors.last_name" class="field-error">{{ errors.last_name }}</small>
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label>Email *</label>
              <InputText
                v-model="form.email"
                placeholder="juan@empresa.com"
                type="email"
                :invalid="!!errors.email"
                fluid
              />
              <small v-if="errors.email" class="field-error">{{ errors.email }}</small>
            </div>
            <div class="field">
              <label>Teléfono</label>
              <InputText
                v-model="form.phone"
                placeholder="+52 55 1234 5678"
                fluid
              />
            </div>
          </div>

          <div class="field-row">
            <div class="field">
              <label>ID externo *</label>
              <InputText
                v-model="form.external_id"
                placeholder="EMP-001"
                :invalid="!!errors.external_id"
                fluid
              />
              <small v-if="errors.external_id" class="field-error">{{ errors.external_id }}</small>
              <small class="field-hint">Identificador en el sistema HR</small>
            </div>
            <div class="field">
              <label>Casos máx. por día</label>
              <InputNumber
                v-model="form.max_cases_per_day"
                :min="1"
                :max="20"
                show-buttons
                fluid
              />
            </div>
          </div>

          <div class="field">
            <label>Especialidades</label>
            <InputChips
              v-model="form.skills"
              placeholder="Escribe y presiona Enter"
              class="skills-chips"
            />
            <small class="field-hint">Ej: auto, hogar, vida, robo</small>
          </div>
        </section>
      </div>

      <Divider style="margin: 0.5rem 0" />

      <!-- Ubicación base — fuera del scroll para que Leaflet calcule offsets correctamente -->
      <section class="form-section map-section">
        <h3 class="section-title">Ubicación base</h3>
        <small class="field-hint" style="display: block; margin-bottom: 0.75rem">
          Domicilio o zona de operación habitual del ajustador
        </small>

        <LocationPicker
          :latitude="form.home_latitude || null"
          :longitude="form.home_longitude || null"
          :visible="visible"
          @update:latitude="form.home_latitude = $event"
          @update:longitude="form.home_longitude = $event"
        />
        <small v-if="errors.location" class="field-error">{{ errors.location }}</small>
      </section>

      <Message v-if="apiError" severity="error" :closable="false">{{ apiError }}</Message>
    </div>

    <template #footer>
      <Button
        label="Cancelar"
        severity="secondary"
        text
        :disabled="submitting"
        @click="visible = false"
      />
      <Button
        label="Crear ajustador"
        icon="pi pi-check"
        :loading="submitting"
        @click="submit"
      />
    </template>
  </Dialog>
</template>

<style scoped>
.form-body {
  display: flex;
  flex-direction: column;
  gap: 0;
}

/* Solo los campos de texto hacen scroll — el mapa queda estático */
.fields-scroll {
  max-height: 40vh;
  overflow-y: auto;
  padding-right: 0.25rem;
}

.map-section {
  flex-shrink: 0;
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  padding: 0.25rem 0 1rem;
}

.section-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--p-surface-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin: 0;
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.field label {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--p-surface-200);
}

.field-error {
  color: var(--p-red-400);
  font-size: 0.78rem;
}

.field-hint {
  color: var(--p-surface-500);
  font-size: 0.78rem;
}

.skills-chips {
  width: 100%;
}
</style>
