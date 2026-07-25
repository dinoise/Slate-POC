<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted, nextTick } from 'vue'
import InputText from 'primevue/inputtext'
import Button from 'primevue/button'
import type * as L from 'leaflet'

const props = defineProps<{
  latitude: number | null
  longitude: number | null
  /** Pass true when the container becomes visible (e.g. dialog opens) so the map can invalidateSize */
  visible?: boolean
}>()

const emit = defineEmits<{
  'update:latitude': [value: number]
  'update:longitude': [value: number]
}>()

const mapEl = ref<HTMLElement | null>(null)
const searchQuery = ref('')
const searching = ref(false)
const searchError = ref('')

let map: L.Map | null = null
let marker: L.Marker | null = null
let defaultIcon: import('leaflet').Icon | null = null

// ── Leaflet init ──────────────────────────────────────────────────────────────

async function initMap() {
  if (map || !mapEl.value) return

  const L = await import('leaflet')
  await import('leaflet/dist/leaflet.css')

  // L.Icon.Default no funciona con Vite porque usa rutas relativas al CSS
  // que el bundler rompe. Definimos el ícono explícitamente con L.icon()
  // usando un SVG inline — sin dependencia de archivos externos.
  const markerSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="24" height="36">
    <path d="M12 0C7.6 0 4 3.6 4 8c0 5.4 8 20 8 20s8-14.6 8-20c0-4.4-3.6-8-8-8z" fill="#6366f1" stroke="#fff" stroke-width="1.5"/>
    <circle cx="12" cy="8" r="3" fill="#fff"/>
  </svg>`
  const markerUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(markerSvg)}`

  defaultIcon = L.icon({
    iconUrl: markerUrl,
    iconSize: [24, 36],
    iconAnchor: [12, 36],
    popupAnchor: [0, -36],
  })

  const center: L.LatLngTuple = props.latitude && props.longitude
    ? [props.latitude, props.longitude]
    : [19.4326, -99.1332] // CDMX default

  map = L.map(mapEl.value).setView(center, props.latitude ? 13 : 10)

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap, © CARTO',
    maxZoom: 19,
  }).addTo(map)

  if (props.latitude && props.longitude) {
    placeMarker(L, props.latitude, props.longitude)
  }

  map.on('click', (e: L.LeafletMouseEvent) => {
    placeMarker(L, e.latlng.lat, e.latlng.lng)
    emit('update:latitude', e.latlng.lat)
    emit('update:longitude', e.latlng.lng)
  })
}

function placeMarker(L: typeof import('leaflet'), lat: number, lng: number) {
  if (!map) return
  if (marker) {
    marker.setLatLng([lat, lng])
  } else {
    marker = L.marker([lat, lng], { draggable: true, icon: defaultIcon ?? undefined }).addTo(map)
    marker.on('dragend', () => {
      const pos = marker!.getLatLng()
      emit('update:latitude', pos.lat)
      emit('update:longitude', pos.lng)
    })
  }
}

// ── Init map once the container has real dimensions ───────────────────────────
// PrimeVue Dialog aplica una transición de entrada — el ref existe en el DOM
// pero el contenedor tiene height:0 hasta que la animación termina.
// Usamos ResizeObserver para esperar a que el div tenga dimensiones reales
// antes de inicializar Leaflet, y llamamos invalidateSize() en aperturas
// subsiguientes (el mapa ya existe pero el Dialog lo ocultó con display:none).

let ro: ResizeObserver | null = null

onMounted(() => {
  ro = new ResizeObserver(async (entries) => {
    const entry = entries[0]
    if (!entry || entry.contentRect.height === 0) return
    if (!map) {
      await initMap()
    } else {
      await nextTick()
      map.invalidateSize()
    }
  })
  if (mapEl.value) ro.observe(mapEl.value)
})

// Cuando el diálogo se vuelve a abrir (visible ya era true antes),
// nextTick + invalidateSize garantiza que los tiles se redibujn.
watch(() => props.visible, async (isVisible) => {
  if (isVisible && map) {
    await nextTick()
    map.invalidateSize()
  }
})

// ── Nominatim geocoding ───────────────────────────────────────────────────────

async function search() {
  if (!searchQuery.value.trim()) return
  searching.value = true
  searchError.value = ''
  try {
    const qs = new URLSearchParams({ q: searchQuery.value, format: 'json', limit: '1' })
    const res = await fetch(`https://nominatim.openstreetmap.org/search?${qs}`, {
      headers: { 'User-Agent': 'slate-poc-admin/1.0' },
    })
    const results = await res.json()
    if (!results.length) {
      searchError.value = 'No se encontró la dirección'
      return
    }
    const { lat, lon } = results[0]
    const latitude = parseFloat(lat)
    const longitude = parseFloat(lon)
    const L = await import('leaflet')
    placeMarker(L, latitude, longitude)
    map?.setView([latitude, longitude], 15)
    emit('update:latitude', latitude)
    emit('update:longitude', longitude)
  } catch {
    searchError.value = 'Error al buscar dirección'
  } finally {
    searching.value = false
  }
}

// ── Geolocation ───────────────────────────────────────────────────────────────

async function useCurrentLocation() {
  if (!navigator.geolocation) return
  navigator.geolocation.getCurrentPosition(async ({ coords }) => {
    const L = await import('leaflet')
    placeMarker(L, coords.latitude, coords.longitude)
    map?.setView([coords.latitude, coords.longitude], 15)
    emit('update:latitude', coords.latitude)
    emit('update:longitude', coords.longitude)
  })
}

// ── Cleanup ───────────────────────────────────────────────────────────────────

onUnmounted(() => {
  ro?.disconnect()
  ro = null
  map?.remove()
  map = null
  marker = null
  defaultIcon = null
})
</script>

<template>
  <div class="location-picker">
    <div class="search-row">
      <InputText
        v-model="searchQuery"
        placeholder="Buscar dirección..."
        class="search-input"
        @keydown.enter="search"
      />
      <Button
        icon="pi pi-search"
        severity="secondary"
        :loading="searching"
        @click="search"
      />
      <Button
        icon="pi pi-map-marker"
        severity="secondary"
        v-tooltip="'Usar mi ubicación'"
        @click="useCurrentLocation"
      />
    </div>

    <p v-if="searchError" class="search-error">{{ searchError }}</p>

    <div ref="mapEl" class="map-container" />

    <p class="coords-display">
      <template v-if="latitude && longitude">
        <span class="pi pi-map-marker" style="margin-right: 0.3rem" />
        {{ latitude.toFixed(6) }}, {{ longitude.toFixed(6) }}
      </template>
      <span v-else class="coords-hint">Haz clic en el mapa para colocar la ubicación base</span>
    </p>
  </div>
</template>

<style scoped>
.location-picker {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.search-row {
  display: flex;
  gap: 0.5rem;
}

.search-input {
  flex: 1;
}

.search-error {
  font-size: 0.8rem;
  color: var(--p-red-400);
  margin: 0;
}

.map-container {
  height: 280px;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--p-surface-700);
}

.coords-display {
  font-size: 0.8rem;
  color: var(--p-surface-300);
  margin: 0;
  min-height: 1.2rem;
}

.coords-hint {
  color: var(--p-surface-500);
  font-style: italic;
}
</style>
