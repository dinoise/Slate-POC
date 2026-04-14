// ─── State ────────────────────────────────────────────────────────────────────
// ROUTE_COLORS, buildRouteLayer, buildCandidateLayer, fetchRoute
// are provided by route-utils.js (loaded before this script).

const state = {
  mode: 'incident',
  adjCount: 0,
  incCount: 0,
  asgnCount: 0,
  markers: new Map(),           // db_id_str -> L.layer
  adjusterData: new Map(),      // adjuster_id (int) -> {id, first_name, ...}
  incidentRoutes: new Map(),    // incident_id (int) -> L.layer  (one route per incident)
  incidentAdjMap: new Map(),    // incident_id (int) -> adjuster_id (int)  (winner per incident)
  incidentCandidates: new Map(),// incident_id (int) -> [{adjuster, travel_time_s, rank}, ...]
  candidateRoutes: new Map(),   // adjuster_id (int) -> L.layer  (dashed routes for non-winner candidates)
  routeColorIndex: 0,
  trafficAware: false,          // populated from API response (supports_traffic flag)
  demandMode: 'heatmap',        // 'heatmap' | 'hexagon'
  demandLayer: null,
  demandVisible: true,
  demandDebounceTimer: null,
}

// ─── Map init ─────────────────────────────────────────────────────────────────
const map = L.map('map', { zoomControl: true }).setView([23.6345, -102.5528], 5)

L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap &copy; CARTO',
  maxZoom: 19,
}).addTo(map)

// Custom panes so markers always render above hexagon/heatmap layers
map.createPane('hexPane');   map.getPane('hexPane').style.zIndex   = 350
map.createPane('markerPane'); map.getPane('markerPane').style.zIndex = 450
map.createPane('arrowPane'); map.getPane('arrowPane').style.zIndex  = 400

// ─── Helpers ──────────────────────────────────────────────────────────────────
function showStatus(msg, type = '') {
  const el = document.getElementById('status-box')
  el.textContent = msg
  el.className = type
}

function updateCounters() {
  document.getElementById('cnt-adj').textContent = state.adjCount
  document.getElementById('cnt-inc').textContent = state.incCount
  document.getElementById('cnt-asgn').textContent = state.asgnCount
}

function setMode(mode) {
  state.mode = mode
  document.getElementById('btn-inc').className =
    'mode-btn' + (mode === 'incident' ? ' active-inc' : '')
  map.getContainer().style.cursor = 'crosshair'
}

async function api(method, url, body) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(url, opts)
  if (!res.ok) {
    const txt = await res.text()
    throw new Error(`${method} ${url} → ${res.status}: ${txt}`)
  }
  return res.json()
}

// ─── Markers ──────────────────────────────────────────────────────────────────
function addAdjusterMarker(adj) {
  const key = `adj-${adj.id}`
  if (state.markers.has(key)) return

  state.adjusterData.set(adj.id, adj)

  const marker = L.circleMarker([adj.home_latitude, adj.home_longitude], {
    radius: 10,
    color: '#fff',
    weight: 2,
    fillColor: '#3b82f6',
    fillOpacity: 0.9,
  }).addTo(map)

  marker.bindPopup(
    `<b>${adj.first_name} ${adj.last_name}</b><br>` +
    `ID: ${adj.id}<br>Estado: ${adj.status}` +
    `<button class="popup-del" onclick="softDeleteAdjuster(${adj.id})">🗑 Dar de baja</button>`
  )

  state.markers.set(key, marker)
}

function highlightOptimal(adjId, adjLat, adjLon, incidentId) {
  const key = `adj-${adjId}`
  const existing = state.markers.get(key)
  if (existing) map.removeLayer(existing)

  const icon = L.divIcon({
    className: '',
    html: '<div class="pulse-marker"></div>',
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  })

  const adj = state.adjusterData.get(adjId)
  const marker = L.marker([adjLat, adjLon], { icon }).addTo(map)
  marker.bindPopup(
    `<b>${adj ? adj.first_name + ' ' + adj.last_name : 'Ajustador óptimo'}</b><br>` +
    `ID: ${adjId}` +
    `<button class="popup-del" onclick="softDeleteAdjuster(${adjId})">🗑 Dar de baja</button>`
  )
  state.markers.set(key, marker)
  state.incidentAdjMap.set(incidentId, adjId)
}

function addIncidentMarker(inc, latlng) {
  const icon = L.divIcon({
    className: '',
    html: '<div style="font-size:22px;line-height:1;filter:drop-shadow(0 1px 3px rgba(0,0,0,.8))">⚠️</div>',
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  })
  const marker = L.marker(latlng, { icon }).addTo(map)
  marker.bindPopup(
    `<b>Siniestro #${inc.id}</b><br>` +
    `Tipo: ${inc.incident_type}<br>Severidad: ${inc.severity}` +
    `<button class="popup-del" onclick="softDeleteIncident(${inc.id})">🗑 Cancelar siniestro</button>`
  )
  state.markers.set(`inc-${inc.id}`, marker)
}

// ─── Route drawing ────────────────────────────────────────────────────────────
// buildRouteLayer, buildCandidateLayer, decodePolyline, fetchRoute
// are provided by route-utils.js (loaded before this script).

async function drawRoute(fromLat, fromLon, toLat, toLon, incidentId) {
  // Remove previous route for this specific incident (if any)
  const existing = state.incidentRoutes.get(incidentId)
  if (existing) { removeRouteLayer(map, existing); state.incidentRoutes.delete(incidentId) }

  // Cycle through color palette (used when no traffic data is available)
  const color = ROUTE_COLORS[state.routeColorIndex % ROUTE_COLORS.length]
  state.routeColorIndex++

  try {
    const { coords, traffic_segments } = await fetchRoute(fromLat, fromLon, toLat, toLon)
    const layer = buildRouteLayer(coords, traffic_segments, color)
    layer.addTo(map)
    state.incidentRoutes.set(incidentId, layer)

  } catch (e) {
    console.warn('Route provider not available:', e.message)
    const layer = L.polyline(
      [[fromLat, fromLon], [toLat, toLon]],
      { color: '#f59e0b', weight: 3, dashArray: '8 8' }
    ).addTo(map)
    state.incidentRoutes.set(incidentId, layer)
    showStatus('⚠️ Proveedor de rutas no disponible — ruta aproximada', 'warn')
    return false
  }
  return true
}

// ─── Candidates panel ─────────────────────────────────────────────────────────
function renderCandidates(candidates, winnerId) {
  // candidates: [{adjuster, travel_time_s, rank, incidentLat, incidentLon}, ...]
  const list = document.getElementById('adj-list')
  if (!candidates.length) {
    list.innerHTML = '<div style="font-size:12px;color:#475569;padding:8px;">Sin ajustadores en rango.</div>'
    return
  }

  const trafficBadge = state.trafficAware
    ? '<span class="traffic-badge">🚦 tráfico real</span>'
    : '<span class="traffic-badge no-traffic">sin tráfico</span>'

  list.innerHTML = `<div class="candidates-header">${trafficBadge}</div>` +
    candidates.map(c => {
      const a = c.adjuster
      const isWinner = a.id === winnerId
      const mins = (c.travel_time_s / 60).toFixed(1)
      const routeActive = state.candidateRoutes.has(a.id)
      return `
        <div class="adj-item${isWinner ? ' winner' : ''}"
             onclick="toggleCandidateRoute(${a.id}, ${a.current_latitude ?? a.home_latitude}, ${a.current_longitude ?? a.home_longitude}, ${c.incidentLat}, ${c.incidentLon})"
             style="cursor:pointer"
             title="Click para ver/ocultar ruta">
          <div class="dot"></div>
          <div class="name">${a.first_name} ${a.last_name}</div>
          <div class="time">${isWinner ? '★ ' : ''}${mins} min${routeActive && !isWinner ? ' 👁' : ''}</div>
        </div>`
    }).join('')
}

async function toggleCandidateRoute(adjId, adjLat, adjLon, incLat, incLon) {
  // Winner route is managed by drawRoute — don't toggle it here
  const existing = state.candidateRoutes.get(adjId)
  if (existing) {
    map.removeLayer(existing)
    state.candidateRoutes.delete(adjId)
    // Re-render to update the 👁 indicator
    _rerenderCandidates()
    return
  }

  try {
    const { coords, traffic_segments } = await fetchRoute(adjLat, adjLon, incLat, incLon)
    const layer = buildCandidateLayer(coords, traffic_segments)
    layer.addTo(map)
    state.candidateRoutes.set(adjId, layer)
    _rerenderCandidates()
  } catch (e) {
    console.warn('Could not draw candidate route:', e.message)
  }
}

// Re-render the sidebar list with current route visibility state
function _rerenderCandidates() {
  // Find the most recently stored candidates (last incident's candidates)
  let lastCandidates = null
  let lastWinnerId = null
  for (const [incId, cs] of state.incidentCandidates) {
    lastCandidates = cs
    lastWinnerId = state.incidentAdjMap.get(incId)
  }
  if (lastCandidates) renderCandidates(lastCandidates, lastWinnerId)
}

function clearRoute() {
  state.incidentRoutes.forEach(layer => removeRouteLayer(map, layer))
  state.incidentRoutes.clear()
  state.candidateRoutes.forEach(layer => removeRouteLayer(map, layer))
  state.candidateRoutes.clear()
  state.routeColorIndex = 0
  showStatus('Rutas eliminadas.')
}


// ─── Add incident + optimize ──────────────────────────────────────────────────
async function addIncident(latlng) {
  state.incCount++
  const payload = {
    external_id: `demo-inc-${Date.now()}`,
    incident_type: 'choque',
    severity: 3,
    latitude: latlng.lat,
    longitude: latlng.lng,
    incident_datetime: new Date().toISOString(),
  }

  showStatus('⚙️ Registrando siniestro...')
  let inc
  try {
    inc = await api('POST', '/api/v1/incidents/', payload)
  } catch (e) {
    state.incCount--
    showStatus(`❌ Error creando siniestro: ${e.message}`, 'err')
    console.error(e)
    return
  }
  addIncidentMarker(inc, latlng)
  updateCounters()

  showStatus('⚙️ Buscando ajustadores disponibles...')
  // Use the active positioning scenario so coordinates reflect the optimized
  // positions, not the static seed. Falls back to "initial" on first load.
  const activeScenario = posState.currentScenario || 'initial'
  const radiusKm = parseFloat(document.getElementById('search-radius-km')?.value ?? '30')
  let adjs
  try {
    adjs = await api(
      'GET',
      `/api/v1/adjusters/available/?latitude=${latlng.lat}&longitude=${latlng.lng}&radius_km=${radiusKm}&limit=20&scenario=${activeScenario}`
    )
  } catch (e) {
    showStatus(`❌ Error buscando ajustadores: ${e.message}`, 'err')
    return
  }

  if (!adjs.length) {
    showStatus(`⚠️ Sin ajustadores disponibles en ${radiusKm} km`, 'warn')
    renderCandidates([], null)
    return
  }

  renderCandidates([], null)
  showStatus(`⚙️ Optimizando (${adjs.length} candidatos, escenario: ${activeScenario})...`)

  const optimizeBody = {
    incidents: [{ incident_id: inc.id, latitude: latlng.lat, longitude: latlng.lng }],
    adjusters: adjs.map(a => ({
      adjuster_id: a.id,
      // current_latitude comes from adjuster_positions for the active scenario;
      // falls back to home_latitude when no position row exists.
      latitude: a.current_latitude ?? a.home_latitude,
      longitude: a.current_longitude ?? a.home_longitude,
    })),
    persist: true,
    top_k: parseInt(document.getElementById('top-k')?.value ?? '5', 10),
    max_travel_min: parseFloat(document.getElementById('max-travel-min')?.value ?? '90'),
  }

  let result
  try {
    result = await api('POST', '/api/v1/assignments/optimize', optimizeBody)
  } catch (e) {
    showStatus(`❌ Error optimizando: ${e.message}`, 'err')
    return
  }

  // Update global traffic flag from response
  state.trafficAware = result.traffic_aware ?? false

  if (!result.assignments.length) {
    showStatus('⚠️ El solver no produjo asignaciones', 'warn')
    renderCandidates([], null)
    return
  }

  // Build candidates list from top-K response, enriched with adjuster data + incident coords
  const adjById = new Map(adjs.map(a => [a.id, a]))
  const candidates = (result.candidates.length ? result.candidates : result.assignments.map(a => ({
    incident_id: a.incident_id, adjuster_id: a.adjuster_id,
    travel_time_s: a.travel_time_s, travel_time_min: a.travel_time_min, rank: 1,
  }))).map(c => ({
    adjuster: adjById.get(c.adjuster_id),
    travel_time_s: c.travel_time_s,
    rank: c.rank,
    incidentLat: latlng.lat,
    incidentLon: latlng.lng,
  })).filter(c => c.adjuster != null)

  // Store candidates for this incident (used when re-rendering on delete)
  state.incidentCandidates.set(inc.id, candidates)

  const winner = result.assignments[0]
  state.asgnCount++
  updateCounters()

  const winnerAdj = adjs.find(a => a.id === winner.adjuster_id)
  renderCandidates(candidates, winner.adjuster_id)

  if (winnerAdj) {
    const winLat = winnerAdj.current_latitude ?? winnerAdj.home_latitude
    const winLon = winnerAdj.current_longitude ?? winnerAdj.home_longitude
    highlightOptimal(winner.adjuster_id, winLat, winLon, inc.id)
    const routeOk = await drawRoute(
      winLat, winLon,
      latlng.lat, latlng.lng,
      inc.id
    )
    if (routeOk) {
      showStatus(
        `✅ ${winnerAdj.first_name} ${winnerAdj.last_name} — ${winner.travel_time_min.toFixed(1)} min`,
        'ok'
      )
    }
  } else {
    showStatus(`✅ Asignado adj ID ${winner.adjuster_id} — ${winner.travel_time_min.toFixed(1)} min`, 'ok')
  }
}

// ─── Map click handler ────────────────────────────────────────────────────────
map.on('click', (e) => {
  addIncident(e.latlng)
})

// ─── Soft delete — individual ────────────────────────────────────────────────
async function softDeleteAdjuster(id) {
  try {
    await fetch(`/api/v1/adjusters/${id}`, { method: 'DELETE' })
    const key = `adj-${id}`
    const m = state.markers.get(key)
    if (m) { map.removeLayer(m); state.markers.delete(key) }
    state.adjCount = Math.max(0, state.adjCount - 1)
    updateCounters()
    showStatus(`✅ Ajustador #${id} dado de baja`, 'ok')
  } catch (e) {
    showStatus(`❌ Error: ${e.message}`, 'err')
  }
}

async function softDeleteIncident(id) {
  try {
    await fetch(`/api/v1/incidents/${id}`, { method: 'DELETE' })

    // Remove incident marker
    const key = `inc-${id}`
    const m = state.markers.get(key)
    if (m) { map.removeLayer(m); state.markers.delete(key) }

    // Remove this incident's route
    const routeLayer = state.incidentRoutes.get(id)
    if (routeLayer) { removeRouteLayer(map, routeLayer); state.incidentRoutes.delete(id) }

    // Restore winner adjuster to normal blue circle marker
    const winnerId = state.incidentAdjMap.get(id)
    if (winnerId != null) {
      const adjKey = `adj-${winnerId}`
      const adjMarker = state.markers.get(adjKey)
      if (adjMarker) map.removeLayer(adjMarker)
      state.markers.delete(adjKey)

      const adj = state.adjusterData.get(winnerId)
      if (adj) addAdjusterMarker(adj)
      state.incidentAdjMap.delete(id)
    }

    // Remove candidate routes for adjusters of this incident
    const candidates = state.incidentCandidates.get(id) || []
    candidates.forEach(c => {
      const layer = state.candidateRoutes.get(c.adjuster.id)
      if (layer) { removeRouteLayer(map, layer); state.candidateRoutes.delete(c.adjuster.id) }
    })
    state.incidentCandidates.delete(id)

    state.incCount = Math.max(0, state.incCount - 1)
    state.asgnCount = Math.max(0, state.asgnCount - 1)
    updateCounters()
    showStatus(`✅ Siniestro #${id} cancelado`, 'ok')
  } catch (e) {
    showStatus(`❌ Error: ${e.message}`, 'err')
  }
}

// ─── Soft delete — bulk ───────────────────────────────────────────────────────
async function clearAllAdjusters() {
  if (!confirm('¿Dar de baja TODOS los ajustadores visibles en el mapa?')) return

  const btn = document.getElementById('btn-clear-adj')
  btn.disabled = true

  const keys = [...state.markers.keys()].filter(k => k.startsWith('adj-'))
  if (!keys.length) { btn.disabled = false; showStatus('Sin ajustadores en mapa.'); return }

  showStatus(`⚙️ Borrando ${keys.length} ajustadores...`)
  let ok = 0, fail = 0
  for (const key of keys) {
    const id = parseInt(key.replace('adj-', ''))
    try {
      await fetch(`/api/v1/adjusters/${id}`, { method: 'DELETE' })
      const m = state.markers.get(key)
      if (m) map.removeLayer(m)
      state.markers.delete(key)
      ok++
    } catch { fail++ }
  }

  state.adjCount = 0
  updateCounters()
  btn.disabled = false
  showStatus(
    fail ? `✅ ${ok} borrados, ⚠️ ${fail} fallaron` : `✅ ${ok} ajustadores dados de baja`,
    fail ? 'warn' : 'ok'
  )
}

async function clearAllIncidents() {
  if (!confirm('¿Cancelar TODOS los siniestros visibles en el mapa?')) return

  const btn = document.getElementById('btn-clear-inc')
  btn.disabled = true

  const keys = [...state.markers.keys()].filter(k => k.startsWith('inc-'))
  if (!keys.length) { btn.disabled = false; showStatus('Sin siniestros en mapa.'); return }

  showStatus(`⚙️ Cancelando ${keys.length} siniestros...`)
  let ok = 0, fail = 0
  for (const key of keys) {
    const id = parseInt(key.replace('inc-', ''))
    try {
      await fetch(`/api/v1/incidents/${id}`, { method: 'DELETE' })
      const m = state.markers.get(key)
      if (m) map.removeLayer(m)
      state.markers.delete(key)
      ok++
    } catch { fail++ }
  }

  // Remove all routes
  state.incidentRoutes.forEach(layer => removeRouteLayer(map, layer))
  state.incidentRoutes.clear()
  state.routeColorIndex = 0

  // Restore all winner adjusters to normal blue circles
  state.incidentAdjMap.forEach((adjId) => {
    const adjKey = `adj-${adjId}`
    const adjMarker = state.markers.get(adjKey)
    if (adjMarker) map.removeLayer(adjMarker)
    state.markers.delete(adjKey)
    const adj = state.adjusterData.get(adjId)
    if (adj) addAdjusterMarker(adj)
  })
  state.incidentAdjMap.clear()
  state.incidentCandidates.clear()
  state.candidateRoutes.forEach(layer => map.removeLayer(layer))
  state.candidateRoutes.clear()

  state.incCount = 0
  state.asgnCount = 0
  updateCounters()
  document.getElementById('adj-list').innerHTML =
    '<div style="font-size:12px;color:#475569;padding:8px;">Sin siniestros aún.</div>'
  btn.disabled = false
  showStatus(
    fail ? `✅ ${ok} cancelados, ⚠️ ${fail} fallaron` : `✅ ${ok} siniestros cancelados`,
    fail ? 'warn' : 'ok'
  )
}

// ─── Load existing adjusters on startup ──────────────────────────────────────
async function loadExisting() {
  try {
    const adjs = await api('GET', '/api/v1/adjusters/?limit=200&is_active=true')
    adjs.forEach(a => addAdjusterMarker(a))
    state.adjCount = adjs.length
    updateCounters()
    if (adjs.length) showStatus(`Cargados ${adjs.length} ajustadores activos.`)
  } catch (e) {
    console.warn('Could not load existing adjusters:', e.message)
  }
}

// ─── Demand predictions ───────────────────────────────────────────────────────
function populateHoraSelector() {
  const sel = document.getElementById('sel-hora')
  const currentHour = new Date().getHours()
  for (let h = 0; h < 24; h++) {
    const opt = document.createElement('option')
    opt.value = h
    opt.textContent = `${String(h).padStart(2, '0')}:00`
    if (h === currentHour) opt.selected = true
    sel.appendChild(opt)
  }
}

async function autoSelectValidSlot() {
  const selHora = document.getElementById('sel-hora')
  const selDia = document.getElementById('sel-dia')
  const testBbox = '14.0,-118.0,33.0,-86.0'

  for (const dia of [selDia.value, '0', '1', '2', '3', '4', '5', '6']) {
    for (const hora of [selHora.value, '23', '14', '8', '12', '18', '0']) {
      try {
        const preds = await api(
          'GET',
          `/api/v1/demand-predictions/?hora_num=${hora}&dia_semana_num=${dia}&bbox=${testBbox}&limit=1`
        )
        if (preds.length > 0) {
          selHora.value = hora
          selDia.value = dia
          return
        }
      } catch (_) { /* ignore */ }
    }
  }
}

function getViewportBbox() {
  const b = map.getBounds()
  return `${b.getSouth()},${b.getWest()},${b.getNorth()},${b.getEast()}`
}

function clearDemandLayer() {
  if (state.demandLayer) {
    try { state.demandLayer.remove() } catch (_) { map.removeLayer(state.demandLayer) }
    state.demandLayer = null
  }
}

async function loadDemandPredictions() {
  if (!state.demandVisible) return

  const hora = document.getElementById('sel-hora').value
  const dia = document.getElementById('sel-dia').value
  const bbox = getViewportBbox()
  const limit = state.demandMode === 'heatmap' ? 5000 : 3000

  let preds
  try {
    preds = await api(
      'GET',
      `/api/v1/demand-predictions/?hora_num=${hora}&dia_semana_num=${dia}&bbox=${bbox}&limit=${limit}`
    )
  } catch (e) {
    console.warn('Could not load demand predictions:', e.message)
    showStatus(`⚠️ Error cargando demanda: ${e.message}`, 'warn')
    return
  }

  // Re-check visibility after async fetch — user may have toggled while waiting.
  if (!state.demandVisible) return

  clearDemandLayer()
  if (!preds.length) {
    showStatus(`ℹ️ Sin predicciones para slot ${String(hora).padStart(2,'0')}:00 día ${dia}`, '')
    return
  }

  showStatus(`📊 ${preds.length} predicciones cargadas`, 'ok')
  if (state.demandMode === 'heatmap') {
    renderHeatmap(preds)
  } else {
    renderHexagons(preds)
  }
}

function renderHeatmap(preds) {
  const maxAbs = Math.max(...preds.map(p => p.pred_abs), 1)
  const points = preds.map(p => [p.lat, p.lon, p.pred_abs / maxAbs])
  state.demandLayer = L.heatLayer(points, {
    radius: 25,
    blur: 15,
    maxZoom: 13,
    gradient: { 0: '#1e3a5f', 0.4: '#fbbf24', 0.7: '#f97316', 1: '#dc2626' },
  }).addTo(map)
}

function demandColor(predAbs) {
  if (predAbs >= 8) return '#dc2626'
  if (predAbs >= 2) return '#f97316'
  return '#fbbf24'
}

function renderHexagons(preds) {
  const layers = preds.map(p => {
    const boundary = h3.cellToBoundary(p.h3_r8)
    const color = demandColor(p.pred_abs)
    return L.polygon(boundary, {
      color,
      weight: 0.5,
      fillColor: color,
      fillOpacity: 0.35,
      pane: 'hexPane',
    }).bindTooltip(
      `H3: ${p.h3_r8}<br>Pred: ${p.pred_abs.toFixed(2)} siniestros`,
      { sticky: true }
    )
  })
  state.demandLayer = L.layerGroup(layers).addTo(map)
}

function setDemandMode(mode) {
  state.demandMode = mode
  document.getElementById('btn-demand-heatmap').className =
    'demand-toggle-btn' + (mode === 'heatmap' ? ' active' : '')
  document.getElementById('btn-demand-hexagon').className =
    'demand-toggle-btn' + (mode === 'hexagon' ? ' active' : '')
  loadDemandPredictions()
}

function onSpreadInput(val) {
  document.getElementById('spread-value').textContent = parseFloat(val).toFixed(1)
}

function onSlotChange() {
  clearTimeout(state.demandDebounceTimer)
  state.demandDebounceTimer = setTimeout(loadDemandPredictions, 300)
  checkSlotForPositioning()
}

function toggleDemandVisibility() {
  state.demandVisible = !state.demandVisible
  const btn = document.getElementById('btn-demand-vis')
  if (state.demandVisible) {
    btn.textContent = '👁 Ocultar capa'
    loadDemandPredictions()
  } else {
    btn.textContent = '👁 Mostrar capa'
    clearDemandLayer()
  }
}

map.on('moveend', () => {
  clearTimeout(state.demandDebounceTimer)
  state.demandDebounceTimer = setTimeout(loadDemandPredictions, 300)
})

// ─── Positioning panel ────────────────────────────────────────────────────────
const posState = {
  currentScenario: null,
  posMarkers: [],
  arrowLayers: [],
  scenarioCounter: 0,
  prevPositions: [],       // positions before last optimization (for toggle)
  lastNewPositions: [],    // positions after last optimization (for toggle)
  lastMovedIds: new Set(), // position ids that moved (for toggle highlight)
  showingMovements: false, // toggle state
}


function clearPosMarkers() {
  posState.posMarkers.forEach(m => map.removeLayer(m))
  posState.posMarkers = []
  posState.arrowLayers.forEach(l => map.removeLayer(l))
  posState.arrowLayers = []
}

// Replace the blue markers from loadExisting() with scenario position markers
// and sync state.adjusterData so incident assignment uses updated coordinates.
function syncAdjustersFromPositions(positions) {
  // Remove existing blue adjuster markers
  for (const [key, marker] of state.markers) {
    if (key.startsWith('adj-')) {
      map.removeLayer(marker)
      state.markers.delete(key)
    }
  }

  // Update adjusterData coordinates to reflect current scenario positions
  positions.forEach(p => {
    const existing = state.adjusterData.get(p.adjuster_id)
    if (existing) {
      existing.home_latitude = p.lat
      existing.home_longitude = p.lon
    } else {
      // Proxy adjuster not yet in adjusterData — add minimal record
      state.adjusterData.set(p.adjuster_id, {
        id: p.adjuster_id,
        first_name: (p.adjuster_name || 'Ajustador ' + p.adjuster_id).split(' ')[0],
        last_name: (p.adjuster_name || '').split(' ').slice(1).join(' '),
        home_latitude: p.lat,
        home_longitude: p.lon,
        status: 'available',
      })
    }
  })
}

function renderPositionMarkers(positions, highlight = new Set(), clear = true) {
  if (clear) clearPosMarkers()

  // Group by h3_r8 — multiple adjusters in the same hex get a single clustered marker
  const byHex = new Map()
  positions.forEach(p => {
    const key = p.h3_r8 || `${p.lat.toFixed(5)},${p.lon.toFixed(5)}`
    if (!byHex.has(key)) byHex.set(key, [])
    byHex.get(key).push(p)
  })

  byHex.forEach(group => {
    // Use centroid of the group (they're in the same hex so coords are very close)
    const lat = group.reduce((s, p) => s + p.lat, 0) / group.length
    const lon = group.reduce((s, p) => s + p.lon, 0) / group.length
    const anyMoved = group.some(p => highlight.has(p.id))
    const allMoved = group.every(p => highlight.has(p.id))
    const count = group.length

    // Color: green if any moved, purple if none moved
    const fillColor = anyMoved ? '#22c55e' : '#6366f1'
    const borderColor = anyMoved ? '#22c55e' : '#fff'
    const baseRadius = anyMoved ? 12 : 9

    const marker = L.circleMarker([lat, lon], {
      radius: baseRadius,
      color: borderColor,
      weight: anyMoved ? 3 : 1.5,
      fillColor,
      fillOpacity: anyMoved ? 0.95 : 0.8,
      pane: 'markerPane',
    }).addTo(map)

    // Badge showing count when more than one adjuster shares the hex
    if (count > 1) {
      const badgeColor = allMoved ? '#16a34a' : anyMoved ? '#ca8a04' : '#4338ca'
      const badge = L.divIcon({
        className: '',
        html: `<div style="
          background:${badgeColor};color:#fff;border-radius:50%;
          width:14px;height:14px;font-size:9px;font-weight:700;
          display:flex;align-items:center;justify-content:center;
          border:1px solid #fff;pointer-events:none;">
          ${count}
        </div>`,
        iconSize: [14, 14],
        iconAnchor: [-4, 14],  // top-right of the circle marker
      })
      const badgeMarker = L.marker([lat, lon], { icon: badge, pane: 'markerPane', interactive: false }).addTo(map)
      posState.posMarkers.push(badgeMarker)
    }

    const names = group.map(p => {
      const name = p.adjuster_name || 'Ajustador ' + p.adjuster_id
      const moved = highlight.has(p.id) ? ' ✦' : ''
      return name + moved
    })
    const tooltipLines = count > 1
      ? [`<b>${count} ajustadores en este hexágono</b>`, ...names, `Escenario: ${group[0].scenario}`]
      : [`<b>${names[0]}</b>`, `Escenario: ${group[0].scenario}`]
    const firstWithScore = group.find(p => p.demand_score != null)
    if (firstWithScore) tooltipLines.push(`Gain: +${firstWithScore.demand_score.toFixed(2)}`)

    marker.bindTooltip(tooltipLines.join('<br>'), { sticky: true })
    posState.posMarkers.push(marker)
  })
}

function drawRelocationArrows(prevById, newPositions, movedNames) {
  // Build a map from adjuster_name → rendered centroid in the destination scenario.
  // Multiple adjusters sharing the same h3_r8 are rendered as one grouped marker,
  // so all arrows from that group must point to the same centroid.
  const destCentroidByName = new Map()
  const byHex = new Map()
  newPositions.forEach(p => {
    const key = p.h3_r8 || `${p.lat.toFixed(5)},${p.lon.toFixed(5)}`
    if (!byHex.has(key)) byHex.set(key, [])
    byHex.get(key).push(p)
  })
  byHex.forEach(group => {
    const lat = group.reduce((s, p) => s + p.lat, 0) / group.length
    const lon = group.reduce((s, p) => s + p.lon, 0) / group.length
    group.forEach(p => destCentroidByName.set(p.adjuster_name || '', { lat, lon }))
  })

  // Similarly compute origin centroid per h3_r8 group in prevById
  const prevByHex = new Map()
  Object.values(prevById).forEach(p => {
    const key = p.h3_r8 || `${p.lat.toFixed(5)},${p.lon.toFixed(5)}`
    if (!prevByHex.has(key)) prevByHex.set(key, [])
    prevByHex.get(key).push(p)
  })
  const originCentroidByName = new Map()
  prevByHex.forEach(group => {
    const lat = group.reduce((s, p) => s + p.lat, 0) / group.length
    const lon = group.reduce((s, p) => s + p.lon, 0) / group.length
    group.forEach(p => originCentroidByName.set(p.adjuster_name || '', { lat, lon }))
  })

  // Draw one arrow per mover, deduplicating arrows that share identical origin+dest
  const drawn = new Set()
  movedNames.forEach(name => {
    const origin = originCentroidByName.get(name)
    const dest = destCentroidByName.get(name)
    if (!origin || !dest) return

    // Skip if origin === dest (adjuster stayed in same hex after optimization)
    if (origin.lat === dest.lat && origin.lon === dest.lon) return

    const dedupeKey = `${origin.lat.toFixed(6)},${origin.lon.toFixed(6)}→${dest.lat.toFixed(6)},${dest.lon.toFixed(6)}`
    if (drawn.has(dedupeKey)) return
    drawn.add(dedupeKey)

    const arrow = L.polyline([[origin.lat, origin.lon], [dest.lat, dest.lon]], {
      color: '#22c55e',
      weight: 2,
      dashArray: '6, 6',
      opacity: 0.75,
      pane: 'arrowPane',
    }).addTo(map)
    posState.arrowLayers.push(arrow)
  })
}

function updateMovementToggle() {
  const btn = document.getElementById('btn-pos-movements')
  if (!btn) return
  const hasMovements = posState.prevPositions.length > 0
  btn.disabled = !hasMovements
  btn.textContent = posState.showingMovements ? '📍 Ver posiciones' : '↔ Ver movimientos'
  btn.className = 'pos-btn pos-btn-movements' + (posState.showingMovements ? ' active' : '')
}

function toggleMovements() {
  if (!posState.prevPositions.length) return
  posState.showingMovements = !posState.showingMovements
  updateMovementToggle()

  clearPosMarkers()
  if (posState.showingMovements) {
    // Show origin (grey) + arrows + destination (green/purple)
    const prevById = {}
    posState.prevPositions.forEach(p => { prevById[p.adjuster_name || ''] = p })
    const movedNames = new Set(
      posState.lastNewPositions
        .filter(p => posState.lastMovedIds.has(p.id))
        .map(p => p.adjuster_name || '')
    )

    // 1. Grey markers at origin positions (only movers)
    posState.prevPositions
      .filter(p => movedNames.has(p.adjuster_name || ''))
      .forEach(p => {
        const marker = L.circleMarker([p.lat, p.lon], {
          radius: 8,
          color: '#94a3b8',
          weight: 1.5,
          fillColor: '#475569',
          fillOpacity: 0.7,
          pane: 'markerPane',
        }).addTo(map)
        marker.bindTooltip(
          `<b>${p.adjuster_name || 'Ajustador'}</b><br>📍 Posición anterior`,
          { sticky: true }
        )
        posState.posMarkers.push(marker)
      })

    // 2. Arrows from origin to destination
    drawRelocationArrows(prevById, posState.lastNewPositions, movedNames)

    // 3. New positions — skip clearPosMarkers since we already cleared and added greys+arrows
    renderPositionMarkers(posState.lastNewPositions, posState.lastMovedIds, false)
  } else {
    renderPositionMarkers(posState.lastNewPositions, posState.lastMovedIds)
  }
}

async function loadInitialPositions() {
  const btn = document.getElementById('btn-pos-load')
  btn.disabled = true
  showStatus('🔄 Reiniciando estado...')
  document.getElementById('pos-info').textContent = 'Reiniciando...'

  // ── Reset: cancel all active incidents + release adjusters ────────────────
  try {
    const [incResult, adjResult] = await Promise.all([
      api('DELETE', '/api/v1/incidents/'),
      api('POST', '/api/v1/adjusters/reset-status'),
    ])
    showStatus(`🔄 Reset: ${incResult.cancelled} siniestros cancelados, ${adjResult.reset} ajustadores liberados`)
  } catch (e) {
    showStatus(`⚠️ Reset parcial: ${e.message}`, 'warn')
  }

  // ── Clear local UI state ──────────────────────────────────────────────────
  state.incidentRoutes.forEach(layer => removeRouteLayer(map, layer))
  state.incidentRoutes.clear()
  state.routeColorIndex = 0
  state.incidentAdjMap.clear()
  state.incidentCandidates.clear()
  state.candidateRoutes.forEach(layer => removeRouteLayer(map, layer))
  state.candidateRoutes.clear()

  // Remove incident markers from map
  for (const [key, marker] of state.markers) {
    if (key.startsWith('inc-')) { map.removeLayer(marker); state.markers.delete(key) }
  }
  // Restore all adj markers to normal blue circles
  for (const [key, marker] of state.markers) {
    if (key.startsWith('adj-')) { map.removeLayer(marker); state.markers.delete(key) }
  }
  state.adjusterData.forEach(adj => addAdjusterMarker(adj))

  state.incCount = 0
  state.asgnCount = 0
  updateCounters()
  document.getElementById('adj-list').innerHTML =
    '<div style="font-size:12px;color:#475569;padding:8px;">Sin siniestros aún.</div>'

  clearPosMarkers()

  // ── Load positioning scenario ─────────────────────────────────────────────
  showStatus('📍 Cargando estado inicial...')
  document.getElementById('pos-info').textContent = 'Cargando...'
  try {
    const positions = await api('GET', '/api/v1/adjuster-positions/scenarios/initial')
    posState.currentScenario = 'initial'
    posState.prevPositions = []
    posState.lastNewPositions = []
    posState.lastMovedIds = new Set()
    posState.showingMovements = false
    updateMovementToggle()

    syncAdjustersFromPositions(positions)
    renderPositionMarkers(positions)


    document.getElementById('pos-info').textContent =
      `${positions.length} ajustadores en estado inicial`
    showStatus(`✅ ${positions.length} ajustadores cargados (estado inicial)`, 'ok')
    document.getElementById('btn-pos-optimize').disabled = false
    checkSlotForPositioning()
  } catch (e) {
    showStatus(`❌ Error: ${e.message}`, 'err')
    document.getElementById('pos-info').textContent = 'Error cargando datos.'
  } finally {
    btn.disabled = false
  }
}

async function optimizePositions() {
  const currentScenario = posState.currentScenario
  if (!currentScenario) return

  const hora = parseInt(document.getElementById('sel-hora').value)
  const dia = parseInt(document.getElementById('sel-dia').value)
  const dias = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

  const btn = document.getElementById('btn-pos-optimize')
  btn.disabled = true
  showStatus('⚡ Ejecutando algoritmo greedy...')
  document.getElementById('pos-info').textContent = 'Optimizando...'

  const prevScenarioName = currentScenario
  posState.scenarioCounter++
  const newScenarioName = `optimized_${dias[dia].toLowerCase()}_${String(hora).padStart(2,'0')}h_${posState.scenarioCounter}`

  try {
    const prevData = await api('GET', `/api/v1/adjuster-positions/scenarios/${prevScenarioName}`)
    const prevById = {}
    prevData.forEach(p => { prevById[p.adjuster_name || ''] = p })

    const spreadFactor = parseFloat(document.getElementById('spread-factor').value)

    const result = await api('POST', '/api/v1/recommendations/', {
      scenario: prevScenarioName,
      hora_num: hora,
      dia_semana_num: dia,
      radio_km: 7.5,
      umbral_gain: 0.5,
      spread_factor: spreadFactor,
      spread_rings: 3,
      save_as_scenario: newScenarioName,
    })

    const newPositions = await api('GET', `/api/v1/adjuster-positions/scenarios/${newScenarioName}`)
    posState.currentScenario = newScenarioName

    const movedNames = new Set(result.recommendations.map(r => r.adjuster_name))
    const movedIds = new Set(newPositions.filter(p => movedNames.has(p.adjuster_name || '')).map(p => p.id))

    // Save state for movement toggle
    posState.prevPositions = prevData
    posState.lastNewPositions = newPositions
    posState.lastMovedIds = movedIds
    posState.showingMovements = false
    updateMovementToggle()

    syncAdjustersFromPositions(newPositions)
    renderPositionMarkers(newPositions, movedIds)

    const info = `${result.adjusters_to_move} movidos de ${result.total_adjusters} — ${dias[dia]} ${String(hora).padStart(2,'0')}:00`
    document.getElementById('pos-info').textContent = info
    showStatus(`✅ Optimización completada: ${info}`, 'ok')
    btn.disabled = false
  } catch (e) {
    showStatus(`❌ Error: ${e.message}`, 'err')
    document.getElementById('pos-info').textContent = 'Error en optimización.'
    btn.disabled = false
  }
}

// ─── Available slots ──────────────────────────────────────────────────────────
let availableSlots = new Set()  // "dia-hora" keys for quick lookup

async function loadAvailableSlots() {
  try {
    const slots = await api('GET', '/api/v1/demand-predictions/available-slots')
    availableSlots = new Set(slots.map(s => `${parseInt(s.dia_semana_num)}-${parseInt(s.hora_num)}`))

    // Mark hora options as disabled if no slot exists for that hora on any day
    const availableHoras = new Set(slots.map(s => s.hora_num))
    document.querySelectorAll('#sel-hora option').forEach(opt => {
      opt.disabled = !availableHoras.has(parseInt(opt.value))
    })

    // Mark dia options as disabled if no slot exists for that day at any hora
    const availableDias = new Set(slots.map(s => s.dia_semana_num))
    document.querySelectorAll('#sel-dia option').forEach(opt => {
      opt.disabled = !availableDias.has(parseInt(opt.value))
    })
  } catch (e) {
    console.warn('Could not load available slots:', e.message)
  }
}

function currentSlotHasData() {
  const hora = parseInt(document.getElementById('sel-hora').value)
  const dia = parseInt(document.getElementById('sel-dia').value)
  return availableSlots.has(`${dia}-${hora}`)
}

function checkSlotForPositioning() {
  const info = document.getElementById('pos-info')
  if (!info) return
  if (posState.currentScenario && !currentSlotHasData()) {
    info.textContent = '⚠️ Sin predicciones para este slot. Elige otro día/hora.'
    info.style.color = '#fb923c'
    document.getElementById('btn-pos-optimize').disabled = true
  } else if (posState.currentScenario) {
    info.style.color = ''
    document.getElementById('btn-pos-optimize').disabled = false
  }
}

// ─── Provider selector ────────────────────────────────────────────────────────
async function loadActiveProvider() {
  try {
    const info = await api('GET', '/api/v1/settings/provider')
    _applyProviderUI(info)
  } catch (e) {
    console.warn('Could not load provider info:', e)
  }
}

async function switchProvider(name) {
  const sel = document.getElementById('provider-select')
  const badge = document.getElementById('provider-badge')
  badge.textContent = '…'
  badge.style.color = '#94a3b8'
  try {
    const info = await api('PUT', '/api/v1/settings/provider', { provider: name })
    _applyProviderUI(info)
    showStatus(`Proveedor cambiado a ${info.provider}`, 'ok')
  } catch (e) {
    showStatus(`Error al cambiar proveedor: ${e.message}`, 'error')
    // Revert selector to current provider
    await loadActiveProvider()
  }
}

function _applyProviderUI(info) {
  const sel = document.getElementById('provider-select')
  const badge = document.getElementById('provider-badge')
  // Sync selector
  for (const opt of sel.options) { opt.selected = opt.value === info.provider }
  // Update traffic badge: live traffic > OSM speeds > static
  state.trafficAware = info.supports_traffic
  if (info.supports_traffic) {
    badge.textContent = '🟢 tráfico'
    badge.style.color = '#22c55e'
    badge.style.borderColor = '#22c55e44'
  } else if (info.speed_aware) {
    badge.textContent = '🟡 vel. OSM'
    badge.style.color = '#f59e0b'
    badge.style.borderColor = '#f59e0b44'
  } else {
    badge.textContent = '⚪ estático'
    badge.style.color = '#94a3b8'
    badge.style.borderColor = '#334155'
  }
}

// ─── Init ─────────────────────────────────────────────────────────────────────
populateHoraSelector()
const spreadEl = document.getElementById('spread-factor')
spreadEl.addEventListener('input', () => onSpreadInput(spreadEl.value))
spreadEl.addEventListener('change', () => onSpreadInput(spreadEl.value))
onSpreadInput(spreadEl.value)
loadExisting()
loadAvailableSlots()
loadActiveProvider()
autoSelectValidSlot().then(() => loadDemandPredictions())
