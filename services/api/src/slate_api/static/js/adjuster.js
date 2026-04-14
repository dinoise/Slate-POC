'use strict';
// Depends on route-utils.js being loaded before this script.

const API = '/api/v1';

const state = {
  adjusterData: null,
  eventSource: null,
  currentAssignmentId: null,
  adjusterMarker: null,
  incidentMarker: null,
  routeLayer: null,
  routeColorIndex: 0,
  routeDrawing: false,   // true while _drawRoute fetch is in-flight
};

// ── Map init ─────────────────────────────────────────────────────────────────
const map = L.map('map').setView([19.4326, -99.1332], 11);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '© OpenStreetMap © CartoDB',
  maxZoom: 19,
}).addTo(map);

const adjIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1;">🔵</div>',
  iconSize: [28, 28], iconAnchor: [14, 14], className: '',
});
const incIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1;">🔴</div>',
  iconSize: [28, 28], iconAnchor: [14, 14], className: '',
});

// ── Load adjusters ────────────────────────────────────────────────────────────
async function loadAdjusters() {
  try {
    const res = await fetch(`${API}/adjusters/?limit=500`);
    const adjusters = await res.json();
    const sel = document.getElementById('sel-adj');
    adjusters.forEach((a) => {
      const opt = document.createElement('option');
      opt.value = a.id;
      opt.textContent = `${a.first_name} ${a.last_name} — ${a.status}`;
      sel.appendChild(opt);
    });
  } catch (e) {
    setStatus('Error cargando ajustadores: ' + e.message);
  }
}

// ── Select adjuster ───────────────────────────────────────────────────────────
async function selectAdjuster(adjId) {
  if (!adjId) return;

  // Close existing SSE
  if (state.eventSource) {
    state.eventSource.close();
    state.eventSource = null;
  }

  // Clear map
  _clearRoute();
  if (state.adjusterMarker) { map.removeLayer(state.adjusterMarker); state.adjusterMarker = null; }
  if (state.incidentMarker) { map.removeLayer(state.incidentMarker); state.incidentMarker = null; }
  document.getElementById('assignment-card').style.display = 'none';
  state.currentAssignmentId = null;
  state.adjusterData = null;

  setBadge('reconnecting', 'Conectando...');

  try {
    const res = await fetch(`${API}/adjusters/${adjId}`);
    if (!res.ok) throw new Error(res.statusText);
    state.adjusterData = await res.json();

    const { home_latitude: lat, home_longitude: lon, first_name, last_name, status } = state.adjusterData;

    document.getElementById('adj-info').innerHTML =
      `<strong>${first_name} ${last_name}</strong><br>Estado: ${status}`;

    if (lat && lon) {
      state.adjusterMarker = L.marker([lat, lon], { icon: adjIcon })
        .bindTooltip(`${first_name} ${last_name}`, { permanent: false })
        .addTo(map);
      map.setView([lat, lon], 13);
    }

    // Load existing active assignment (if any) before opening SSE
    await _loadActiveAssignment(adjId);

    // Open SSE stream
    _openSSE(adjId);
  } catch (e) {
    setStatus('Error: ' + e.message);
    setBadge('', 'Error');
  }
}

// ── Load existing active assignment ──────────────────────────────────────────
async function _loadActiveAssignment(adjId) {
  const ACTIVE = new Set(['assigned', 'accepted', 'en_route', 'arrived', 'in_progress']);
  try {
    const res = await fetch(`${API}/assignments/by-adjuster/${adjId}?limit=50`);
    if (!res.ok) return;
    const assignments = await res.json();
    const active = assignments.find(a => ACTIVE.has(a.status));
    if (!active) return;

    const incRes = await fetch(`${API}/incidents/${active.incident_id}`);
    if (!incRes.ok) return;
    const incident = await incRes.json();

    await onAssignment({
      assignment_id:       active.id,
      incident_type:       incident.incident_type,
      severity:            incident.severity,
      address:             incident.address,
      latitude:            incident.latitude,
      longitude:           incident.longitude,
      distance_km:         active.distance_km,
      travel_time_minutes: active.travel_time_minutes,
      current_status:      active.status,
    });
  } catch (e) {
    console.warn('Could not load active assignment:', e);
  }
}

// ── SSE stream ────────────────────────────────────────────────────────────────
function _openSSE(adjId) {
  const es = new EventSource(`${API}/notifications/stream?adjuster_id=${adjId}`);
  state.eventSource = es;

  es.addEventListener('connected', () => {
    setBadge('connected', 'Conectado');
    setStatus('Esperando asignaciones...');
  });

  es.addEventListener('assignment', (event) => {
    const data = JSON.parse(event.data);
    onAssignment(data);
  });

  es.onerror = () => {
    // Browser auto-reconnects — just update badge
    setBadge('reconnecting', 'Reconectando...');
  };
}

// ── Handle new/existing assignment ───────────────────────────────────────────
async function onAssignment(data) {
  state.currentAssignmentId = data.assignment_id;

  // Update card fields
  document.getElementById('inc-type').textContent =
    '🚨 ' + (data.incident_type || '—').replace(/_/g, ' ');
  document.getElementById('inc-severity').innerHTML =
    `Severidad: <strong>${data.severity}/5</strong>`;
  document.getElementById('inc-address').innerHTML =
    `📍 <strong>${data.address || 'Sin dirección'}</strong>`;
  document.getElementById('inc-distance').innerHTML =
    data.distance_km
      ? `Distancia: <strong>${data.distance_km.toFixed(1)} km</strong>`
      : '';
  document.getElementById('inc-travel').innerHTML =
    data.travel_time_minutes
      ? `Tiempo estimado: <strong>${data.travel_time_minutes} min</strong>`
      : '';

  // Show correct action button based on current status
  // SSE payload uses "status"; _loadActiveAssignment uses "current_status"
  const currentStatus = data.current_status || data.status || 'assigned';
  document.getElementById('btn-accept').style.display  = currentStatus === 'assigned'                         ? 'block' : 'none';
  document.getElementById('btn-enroute').style.display = currentStatus === 'accepted'                         ? 'block' : 'none';
  document.getElementById('btn-arrived').style.display = currentStatus === 'en_route'                         ? 'block' : 'none';
  document.getElementById('btn-done').style.display    = ['arrived', 'in_progress'].includes(currentStatus)   ? 'block' : 'none';

  document.getElementById('assignment-card').style.display = 'block';
  setStatus('Asignación activa.');

  // Place incident marker
  if (data.latitude && data.longitude) {
    if (state.incidentMarker) map.removeLayer(state.incidentMarker);
    state.incidentMarker = L.marker([data.latitude, data.longitude], { icon: incIcon })
      .bindTooltip(data.incident_type || 'Siniestro', { permanent: false })
      .addTo(map);
  }

  // Draw route using the shared route-utils pipeline
  if (state.adjusterData && data.latitude && data.longitude) {
    await _drawRoute(
      state.adjusterData.home_latitude,
      state.adjusterData.home_longitude,
      data.latitude,
      data.longitude,
    );
  }
}

// ── Route rendering (uses route-utils.js) ────────────────────────────────────
async function _drawRoute(originLat, originLon, destLat, destLon) {
  if (originLat == null || destLat == null) return;
  _clearRoute();

  const color = ROUTE_COLORS[state.routeColorIndex % ROUTE_COLORS.length];
  state.routeColorIndex++;
  state.routeDrawing = true;

  try {
    const { coords, traffic_segments } = await fetchRoute(originLat, originLon, destLat, destLon);

    // If cancelled while the fetch was in flight, don't add the layer
    if (!state.routeDrawing) return;

    state.routeLayer = buildRouteLayer(coords, traffic_segments, color);
    state.routeLayer.addTo(map);
    const bounds = state.routeLayer.getBounds
      ? state.routeLayer.getBounds()
      : L.latLngBounds([[originLat, originLon], [destLat, destLon]]);
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [40, 40] });
  } catch (e) {
    if (!state.routeDrawing) return;
    console.warn('Route fetch error:', e.message);
    state.routeLayer = L.polyline(
      [[originLat, originLon], [destLat, destLon]],
      { color: '#f59e0b', weight: 3, dashArray: '8 8' }
    ).addTo(map);
    map.fitBounds(state.routeLayer.getBounds(), { padding: [40, 40] });
  } finally {
    state.routeDrawing = false;
  }
}

function _clearRoute() {
  state.routeDrawing = false;   // abort any in-flight draw
  removeRouteLayer(map, state.routeLayer);
  state.routeLayer = null;
}

// ── Update assignment status ──────────────────────────────────────────────────
async function updateStatus(newStatus) {
  if (!state.currentAssignmentId) return;

  try {
    const res = await fetch(`${API}/assignments/${state.currentAssignmentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    if (!res.ok) throw new Error(res.statusText);

    setStatus(`Estado actualizado: ${newStatus.replace('_', ' ')}`);

    // Button progression
    if (newStatus === 'accepted') {
      document.getElementById('btn-accept').style.display  = 'none';
      document.getElementById('btn-enroute').style.display = 'block';
    } else if (newStatus === 'en_route') {
      document.getElementById('btn-enroute').style.display = 'none';
      document.getElementById('btn-arrived').style.display = 'block';
    } else if (newStatus === 'arrived') {
      document.getElementById('btn-arrived').style.display = 'none';
      document.getElementById('btn-done').style.display    = 'block';
    }
  } catch (e) {
    setStatus('Error actualizando estado: ' + e.message);
  }
}

// ── Cancel assignment ─────────────────────────────────────────────────────────
async function cancelAssignment() {
  if (!state.currentAssignmentId) return;
  if (!confirm('¿Cancelar esta asignación y liberar al ajustador?')) return;

  try {
    const res = await fetch(`${API}/assignments/${state.currentAssignmentId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'cancelled' }),
    });
    if (!res.ok) throw new Error(res.statusText);

    document.getElementById('assignment-card').style.display = 'none';
    state.currentAssignmentId = null;
    _clearRoute();
    if (state.incidentMarker) { map.removeLayer(state.incidentMarker); state.incidentMarker = null; }

    setStatus('Asignación cancelada. Esperando nuevas asignaciones...');
  } catch (e) {
    setStatus('Error al cancelar: ' + e.message);
  }
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setBadge(cls, text) {
  const badge = document.getElementById('status-badge');
  badge.className = 'badge' + (cls ? ' ' + cls : '');
  badge.textContent = text;
}

function setStatus(msg) {
  document.getElementById('status-box').textContent = msg;
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadAdjusters();
