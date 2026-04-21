<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import * as L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { useRouter } from 'vue-router'
import { useGoogleAuth } from '@slate/composables'
import { useReporterSessionStore } from '@/stores/reporterSession'
import type { IncidentType, SeverityLevel } from '@slate/types'

const router = useRouter()
const store = useReporterSessionStore()
const { user, signOut } = useGoogleAuth()

// ── Map ───────────────────────────────────────────────────────────────────────
const mapContainer = ref<HTMLElement>()
let map: L.Map | null = null
let pinMarker: L.Marker | null = null

const pinIcon = L.divIcon({
  html: '<div style="font-size:32px;line-height:1;filter:drop-shadow(0 2px 4px rgba(0,0,0,.5));">📍</div>',
  iconSize: [32, 32],
  iconAnchor: [16, 32],
  className: '',
})

onMounted(() => {
  if (!mapContainer.value) return
  map = L.map(mapContainer.value).setView([19.4326, -99.1332], 12)
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap © CartoDB',
    maxZoom: 19,
  }).addTo(map)

  map.on('click', (e: L.LeafletMouseEvent) => {
    placePin(e.latlng.lat, e.latlng.lng)
    // Reverse-geocode address (best-effort via Nominatim)
    reverseGeocode(e.latlng.lat, e.latlng.lng)
  })
})

onUnmounted(() => {
  map?.remove()
  map = null
})

function placePin(lat: number, lng: number) {
  if (!map) return
  form.value.latitude = lat
  form.value.longitude = lng
  if (pinMarker) map.removeLayer(pinMarker)
  pinMarker = L.marker([lat, lng], { icon: pinIcon }).addTo(map)
  map.panTo([lat, lng])
}

async function reverseGeocode(lat: number, lng: number) {
  try {
    const res = await fetch(
      `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lng}&format=json`,
      { headers: { 'Accept-Language': 'es' } },
    )
    const data = await res.json()
    if (data.display_name) form.value.address = data.display_name
  } catch {
    // silent — user can type address manually
  }
}

// ── Geolocation ───────────────────────────────────────────────────────────────
const locating = ref(false)
const locError = ref<string | null>(null)

function useCurrentLocation() {
  if (!('geolocation' in navigator)) {
    locError.value = 'Tu dispositivo no soporta geolocalización'
    return
  }
  locating.value = true
  locError.value = null
  navigator.geolocation.getCurrentPosition(
    (pos) => {
      locating.value = false
      placePin(pos.coords.latitude, pos.coords.longitude)
      reverseGeocode(pos.coords.latitude, pos.coords.longitude)
      map?.setView([pos.coords.latitude, pos.coords.longitude], 15)
    },
    (err) => {
      locating.value = false
      locError.value = err.message
    },
    { enableHighAccuracy: true, timeout: 10_000 },
  )
}

// ── Form ──────────────────────────────────────────────────────────────────────
const form = ref({
  incident_type: 'collision' as IncidentType,
  severity: 3 as SeverityLevel,
  description: '',
  address: '',
  latitude: null as number | null,
  longitude: null as number | null,
})

const incidentTypes: { value: IncidentType; label: string; emoji: string }[] = [
  { value: 'collision', label: 'Colisión', emoji: '🚗' },
  { value: 'theft', label: 'Robo', emoji: '🔓' },
  { value: 'fire', label: 'Incendio', emoji: '🔥' },
  { value: 'flood', label: 'Inundación', emoji: '🌊' },
  { value: 'vandalism', label: 'Vandalismo', emoji: '🔨' },
  { value: 'other', label: 'Otro', emoji: '📌' },
]

const severityLabels: Record<SeverityLevel, string> = {
  1: 'Muy leve',
  2: 'Leve',
  3: 'Moderado',
  4: 'Grave',
  5: 'Crítico',
}

const canSubmit = computed(
  () => form.value.latitude !== null && form.value.longitude !== null && form.value.address.trim(),
)

// Modal state
const showForm = ref(false)
// Local guard — set synchronously before any await so double-tap on mobile
// cannot fire a second submission before Vue re-renders the disabled button.
const submitting = ref(false)

async function submit() {
  if (!canSubmit.value || !user.value || submitting.value) return
  submitting.value = true
  try {
    const incident = await store.submitIncident({
      incident_type: form.value.incident_type,
      severity: form.value.severity,
      description: form.value.description,
      address: form.value.address,
      latitude: form.value.latitude!,
      longitude: form.value.longitude!,
    })
    showForm.value = false
    router.push(`/track/${incident.id}`)
  } catch {
    // error shown via store.error
    submitting.value = false
  }
}

// Open form automatically once location is set via click
watch(
  () => form.value.latitude,
  (lat) => { if (lat !== null && !showForm.value) showForm.value = true },
)
</script>

<template>
  <div class="reporter-layout">
    <!-- Top nav -->
    <div class="navbar bg-base-100 shadow-sm px-4 min-h-12">
      <div class="flex-1">
        <span class="text-sm font-bold">📋 Slate Reporter</span>
      </div>
      <div class="flex-none gap-2">
        <div v-if="user" class="dropdown dropdown-end">
          <div tabindex="0" role="button" class="btn btn-ghost btn-circle btn-sm avatar">
            <div class="w-8 rounded-full">
              <img v-if="user.picture" :src="user.picture" :alt="user.name" />
              <div v-else class="bg-neutral text-neutral-content flex items-center justify-center w-full h-full text-xs">
                {{ user.name.charAt(0) }}
              </div>
            </div>
          </div>
          <ul tabindex="0" class="menu menu-sm dropdown-content bg-base-100 rounded-box z-10 mt-3 w-52 p-2 shadow">
            <li class="menu-title text-xs">{{ user.email }}</li>
            <li><button @click="signOut">Cerrar sesión</button></li>
          </ul>
        </div>
      </div>
    </div>

    <!-- Map fills remaining space -->
    <div ref="mapContainer" class="reporter-map" />

    <!-- Floating location hint (shown when no pin placed) -->
    <div
      v-if="form.latitude === null"
      class="absolute bottom-24 left-1/2 -translate-x-1/2 z-[500] pointer-events-none"
    >
      <div class="badge badge-neutral badge-lg gap-2 shadow-lg px-4 py-3 text-sm">
        <span>Toca el mapa o usa tu ubicación</span>
      </div>
    </div>

    <!-- Bottom action bar -->
    <div class="absolute bottom-0 left-0 right-0 z-[500] p-4 flex gap-3 bg-gradient-to-t from-base-300/90 to-transparent">
      <button
        class="btn btn-outline btn-sm flex-none"
        :class="locating ? 'loading' : ''"
        :disabled="locating"
        @click="useCurrentLocation"
      >
        <span v-if="!locating">📍 Mi ubicación</span>
        <span v-else>Buscando…</span>
      </button>
      <button
        v-if="form.latitude !== null"
        class="btn btn-primary flex-1"
        @click="showForm = true"
      >
        Reportar siniestro
      </button>
    </div>

    <!-- Loc error toast -->
    <div v-if="locError" class="toast toast-top toast-center z-[600]">
      <div class="alert alert-error text-sm">
        <span>{{ locError }}</span>
        <button class="btn btn-ghost btn-xs" @click="locError = null">✕</button>
      </div>
    </div>

    <!-- Incident form modal (bottom sheet on mobile) -->
    <dialog :open="showForm" class="modal modal-bottom sm:modal-middle">
      <div class="modal-box max-h-[90dvh] overflow-y-auto">
        <h3 class="font-bold text-lg mb-4">Nuevo siniestro</h3>

        <!-- Type selector -->
        <fieldset class="fieldset mb-3">
          <legend class="fieldset-legend">Tipo de siniestro</legend>
          <div class="grid grid-cols-3 gap-2">
            <label
              v-for="t in incidentTypes"
              :key="t.value"
              class="flex flex-col items-center gap-1 p-2 rounded-lg border cursor-pointer transition-colors"
              :class="form.incident_type === t.value
                ? 'border-primary bg-primary/10 text-primary'
                : 'border-base-300 hover:border-base-content/30'"
            >
              <input
                v-model="form.incident_type"
                type="radio"
                :value="t.value"
                class="sr-only"
              />
              <span class="text-2xl">{{ t.emoji }}</span>
              <span class="text-xs font-medium">{{ t.label }}</span>
            </label>
          </div>
        </fieldset>

        <!-- Severity -->
        <fieldset class="fieldset mb-3">
          <legend class="fieldset-legend">Severidad — {{ severityLabels[form.severity] }}</legend>
          <input
            v-model.number="form.severity"
            type="range"
            min="1"
            max="5"
            step="1"
            class="range range-primary range-sm w-full"
          />
          <div class="flex justify-between text-xs text-base-content/50 px-1 mt-1">
            <span>Muy leve</span>
            <span>Crítico</span>
          </div>
        </fieldset>

        <!-- Address -->
        <fieldset class="fieldset mb-3">
          <legend class="fieldset-legend">Dirección</legend>
          <input
            v-model="form.address"
            type="text"
            placeholder="Calle, número, colonia…"
            class="input input-bordered w-full"
          />
        </fieldset>

        <!-- Description -->
        <fieldset class="fieldset mb-4">
          <legend class="fieldset-legend">Descripción (opcional)</legend>
          <textarea
            v-model="form.description"
            placeholder="Describe brevemente lo ocurrido…"
            class="textarea textarea-bordered w-full"
            rows="3"
          />
        </fieldset>

        <!-- Error -->
        <div v-if="store.error" role="alert" class="alert alert-error text-sm mb-3">
          <span>{{ store.error }}</span>
        </div>

        <div class="modal-action gap-2">
          <button class="btn btn-ghost" @click="showForm = false">Cancelar</button>
          <button
            class="btn btn-primary flex-1"
            :class="store.loading || submitting ? 'loading' : ''"
            :disabled="!canSubmit || store.loading || submitting"
            @click="submit"
          >
            {{ store.loading ? 'Enviando…' : 'Enviar reporte' }}
          </button>
        </div>
      </div>
      <form method="dialog" class="modal-backdrop" @submit.prevent="showForm = false">
        <button>close</button>
      </form>
    </dialog>
  </div>
</template>

<style scoped>
.reporter-layout {
  position: relative;
  height: 100dvh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.reporter-map {
  flex: 1;
  min-height: 0;
}
</style>
