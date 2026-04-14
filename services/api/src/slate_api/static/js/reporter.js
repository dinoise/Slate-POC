'use strict';
// Depends on route-utils.js being loaded before this script.

const API = '/api/v1';

const state = {
  lat: null,
  lon: null,
  marker: null,           // incident placement marker (new report)
  // per active-incident markers: incidentId -> { incMarker, adjMarker, routeLayer }
  activeMarkers: new Map(),
  pollTimers: new Map(),  // incidentId -> setInterval id
};

// ── Map init ──────────────────────────────────────────────────────────────────
const map = L.map('map').setView([19.4326, -99.1332], 11);
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
  attribution: '© OpenStreetMap © CartoDB',
  maxZoom: 19,
}).addTo(map);

const newIncidentIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1;">📍</div>',
  iconSize: [28, 28], iconAnchor: [14, 14], className: '',
});
const incidentIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1;">🔴</div>',
  iconSize: [28, 28], iconAnchor: [14, 14], className: '',
});
const adjusterIcon = L.divIcon({
  html: '<div style="font-size:24px;line-height:1;">🔵</div>',
  iconSize: [28, 28], iconAnchor: [14, 14], className: '',
});

map.on('click', (e) => {
  state.lat = e.latlng.lat;
  state.lon = e.latlng.lng;
  if (state.marker) {
    state.marker.setLatLng(e.latlng);
  } else {
    state.marker = L.marker(e.latlng, { icon: newIncidentIcon }).addTo(map);
  }
  document.getElementById('coords-display').innerHTML =
    `📍 ${state.lat.toFixed(6)}, ${state.lon.toFixed(6)}`;
  _checkReady();
});

// ── Load users ────────────────────────────────────────────────────────────────
async function loadUsers() {
  try {
    const res = await fetch(`${API}/users/?limit=500`);
    const users = await res.json();
    const sel = document.getElementById('sel-user');
    users.forEach((u) => {
      const opt = document.createElement('option');
      opt.value = u.id;
      opt.textContent = `${u.first_name} ${u.last_name} — ${u.email}`;
      sel.appendChild(opt);
    });
  } catch (e) {
    setStatus('Error al cargar usuarios: ' + e.message);
  }
}

document.getElementById('sel-user').addEventListener('change', (e) => {
  _checkReady();
  const userId = parseInt(e.target.value, 10);
  if (userId) loadActiveIncidents(userId);
  else {
    document.getElementById('active-incidents-section').style.display = 'none';
    _clearAllActiveMarkers();
  }
});

function _checkReady() {
  const userSelected = document.getElementById('sel-user').value !== '';
  const locationSet = state.lat !== null;
  document.getElementById('btn-submit').disabled = !(userSelected && locationSet);
}

// ── Active incidents for selected user ───────────────────────────────────────
const ACTIVE_STATUSES = new Set(['pending', 'assigned', 'accepted', 'en_route', 'arrived', 'in_progress']);

async function loadActiveIncidents(userId) {
  try {
    const res = await fetch(`${API}/incidents/?limit=500`);
    if (!res.ok) return;
    const all = await res.json();
    const active = all.filter(inc =>
      inc.reported_by_user_id === userId && ACTIVE_STATUSES.has(inc.status)
    );

    document.getElementById('active-incidents-section').style.display =
      active.length > 0 ? 'block' : 'none';

    // Stop polling for incidents no longer in the list
    for (const [id] of state.pollTimers) {
      if (!active.find(i => i.id === id)) _stopPolling(id);
    }

    _renderActiveIncidents(active);

    // Ensure polling is running for each active incident
    for (const inc of active) {
      if (!state.pollTimers.has(inc.id)) _startPolling(inc.id, userId);
    }
  } catch (e) {
    console.warn('loadActiveIncidents error:', e);
  }
}

function _renderActiveIncidents(incidents) {
  const list = document.getElementById('active-incidents-list');
  if (incidents.length === 0) { list.innerHTML = ''; return; }

  list.innerHTML = incidents.map(inc => `
    <div class="incident-card ${inc.status === 'assigned' || inc.status === 'accepted' || inc.status === 'en_route' ? 'assigned' : ''}"
         id="inc-card-${inc.id}">
      <div class="ic-header">
        <span class="ic-type">🚨 ${(inc.incident_type || '—').replace(/_/g, ' ')}</span>
        <span class="ic-status ${inc.status}" id="ic-status-${inc.id}">${_statusLabel(inc.status)}</span>
      </div>
      <div class="ic-field">Severidad: <strong>${inc.severity}/5</strong></div>
      ${inc.address ? `<div class="ic-field">📍 <strong>${inc.address}</strong></div>` : ''}
      <div class="ic-field" style="color:#475569;font-size:10px;">ID #${inc.id}</div>
      <div id="adj-info-${inc.id}"></div>
      <button class="btn-cancel-inc" onclick="cancelIncident(${inc.id})">✖ Cancelar siniestro</button>
    </div>
  `).join('');

  // Draw markers for all active incidents
  for (const inc of incidents) {
    _ensureIncidentMarker(inc);
  }
}

function _statusLabel(status) {
  const labels = {
    pending: 'Pendiente',
    assigned: 'Ajustador asignado',
    accepted: 'Aceptado',
    en_route: 'En camino',
    arrived: 'Llegó',
    in_progress: 'En atención',
    completed: 'Completado',
    cancelled: 'Cancelado',
  };
  return labels[status] || status;
}

// ── Markers & route for each active incident ──────────────────────────────────
function _ensureIncidentMarker(inc) {
  if (!state.activeMarkers.has(inc.id)) {
    const incMarker = L.marker([inc.latitude, inc.longitude], { icon: incidentIcon })
      .bindTooltip(`#${inc.id} — ${(inc.incident_type || '').replace(/_/g, ' ')}`, { permanent: false })
      .addTo(map);
    state.activeMarkers.set(inc.id, { incMarker, adjMarker: null, routeLayer: null });
  }
}

async function _updateAdjusterInfo(incId, assignment) {
  const entry = state.activeMarkers.get(incId);
  if (!entry) return;

  try {
    const res = await fetch(`${API}/adjusters/${assignment.adjuster_id}`);
    if (!res.ok) return;
    const adj = await res.json();

    const adjInfoEl = document.getElementById(`adj-info-${incId}`);
    if (adjInfoEl) {
      adjInfoEl.innerHTML = `
        <div class="adjuster-info">
          <div class="adj-name">🔵 ${adj.first_name} ${adj.last_name}</div>
          <div style="color:#64748b;margin-top:2px;">${adj.phone || ''}</div>
          ${assignment.travel_time_minutes
            ? `<div style="color:#94a3b8;margin-top:2px;">⏱ ~${assignment.travel_time_minutes} min</div>`
            : ''}
        </div>`;
    }

    // Adjuster position: prefer current_latitude, fall back to home
    const adjLat = adj.current_latitude ?? adj.home_latitude;
    const adjLon = adj.current_longitude ?? adj.home_longitude;

    // Place or move adjuster marker
    if (entry.adjMarker) {
      entry.adjMarker.setLatLng([adjLat, adjLon]);
    } else {
      entry.adjMarker = L.marker([adjLat, adjLon], { icon: adjusterIcon })
        .bindTooltip(`${adj.first_name} ${adj.last_name}`, { permanent: false })
        .addTo(map);
      entry.adjMarker.bindTooltip(`${adj.first_name} ${adj.last_name}`, { permanent: false });
    }

    // Draw route adjuster → incident (only if not already drawn)
    if (!entry.routeLayer) {
      const inc = entry.incMarker.getLatLng();
      try {
        const { coords, traffic_segments } = await fetchRoute(adjLat, adjLon, inc.lat, inc.lng);
        entry.routeLayer = buildRouteLayer(coords, traffic_segments, '#6366f1');
        entry.routeLayer.addTo(map);
      } catch (_) {
        entry.routeLayer = L.polyline(
          [[adjLat, adjLon], [inc.lat, inc.lng]],
          { color: '#6366f1', weight: 2, dashArray: '6 8', opacity: 0.7 }
        ).addTo(map);
      }
    }
  } catch (e) {
    console.warn('_updateAdjusterInfo error:', e);
  }
}

function _clearIncidentMarkers(incId) {
  const entry = state.activeMarkers.get(incId);
  if (!entry) return;
  if (entry.incMarker) map.removeLayer(entry.incMarker);
  if (entry.adjMarker) map.removeLayer(entry.adjMarker);
  removeRouteLayer(map, entry.routeLayer);
  state.activeMarkers.delete(incId);
}

function _clearAllActiveMarkers() {
  for (const [id] of state.activeMarkers) _clearIncidentMarkers(id);
  for (const [id] of state.pollTimers) _stopPolling(id);
}

// ── Polling per incident ──────────────────────────────────────────────────────
function _startPolling(incId, userId) {
  const timer = setInterval(() => _pollIncident(incId, userId), 5000);
  state.pollTimers.set(incId, timer);
  // Run immediately too
  _pollIncident(incId, userId);
}

function _stopPolling(incId) {
  const timer = state.pollTimers.get(incId);
  if (timer) clearInterval(timer);
  state.pollTimers.delete(incId);
}

async function _pollIncident(incId, userId) {
  try {
    const res = await fetch(`${API}/incidents/${incId}`);
    if (!res.ok) { _stopPolling(incId); return; }
    const inc = await res.json();

    // If no longer active, remove from UI
    if (!ACTIVE_STATUSES.has(inc.status)) {
      _stopPolling(incId);
      _clearIncidentMarkers(incId);
      const card = document.getElementById(`inc-card-${incId}`);
      if (card) card.remove();
      // Hide section if empty
      if (document.getElementById('active-incidents-list').children.length === 0) {
        document.getElementById('active-incidents-section').style.display = 'none';
      }
      return;
    }

    // Update status badge
    const statusEl = document.getElementById(`ic-status-${incId}`);
    if (statusEl) {
      statusEl.textContent = _statusLabel(inc.status);
      statusEl.className = `ic-status ${inc.status}`;
    }

    // Update card border
    const card = document.getElementById(`inc-card-${incId}`);
    if (card) {
      const isAssigned = ['assigned', 'accepted', 'en_route', 'arrived', 'in_progress'].includes(inc.status);
      card.className = `incident-card${isAssigned ? ' assigned' : ''}`;
    }

    // If assigned, fetch the active assignment to show adjuster info
    if (['assigned', 'accepted', 'en_route', 'arrived', 'in_progress'].includes(inc.status)) {
      const aRes = await fetch(`${API}/assignments/by-incident/${incId}`);
      if (aRes.ok) {
        const assignments = await aRes.json();
        const assignment = assignments.find(a => !['cancelled', 'completed'].includes(a.status));
        if (assignment) await _updateAdjusterInfo(incId, assignment);
      }
    }
  } catch (e) {
    console.warn('_pollIncident error:', e);
  }
}

// ── Cancel incident ───────────────────────────────────────────────────────────
async function cancelIncident(incId) {
  if (!confirm('¿Cancelar este siniestro?')) return;
  try {
    const res = await fetch(`${API}/incidents/${incId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error(res.statusText);

    _stopPolling(incId);
    _clearIncidentMarkers(incId);
    const card = document.getElementById(`inc-card-${incId}`);
    if (card) card.remove();

    if (document.getElementById('active-incidents-list').children.length === 0) {
      document.getElementById('active-incidents-section').style.display = 'none';
    }
    setStatus('Siniestro cancelado.');
  } catch (e) {
    setStatus('Error al cancelar: ' + e.message);
  }
}

// ── Submit new incident ───────────────────────────────────────────────────────
async function submitIncident() {
  const userId = parseInt(document.getElementById('sel-user').value, 10);
  if (!userId || state.lat === null) return;

  document.getElementById('btn-submit').disabled = true;
  setStatus('Enviando siniestro...');

  const payload = {
    external_id: crypto.randomUUID(),
    incident_type: document.getElementById('sel-type').value,
    severity: parseInt(document.getElementById('sev').value, 10),
    description: document.getElementById('desc').value || null,
    latitude: state.lat,
    longitude: state.lon,
    address: document.getElementById('addr').value || null,
    incident_datetime: new Date().toISOString(),
    reported_by_user_id: userId,
  };

  try {
    const res = await fetch(`${API}/incidents/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || res.statusText);
    }
    const incident = await res.json();
    resetForm();
    setStatus(`✅ Siniestro #${incident.id} registrado. Buscando ajustador...`);
    // Refresh active incidents immediately
    await loadActiveIncidents(userId);
  } catch (e) {
    setStatus('❌ Error: ' + e.message);
    document.getElementById('btn-submit').disabled = false;
  }
}

function resetForm() {
  if (state.marker) { map.removeLayer(state.marker); state.marker = null; }
  state.lat = null;
  state.lon = null;
  document.getElementById('coords-display').innerHTML =
    '📍 Haz click en el mapa para ubicar el siniestro';
  document.getElementById('desc').value = '';
  document.getElementById('addr').value = '';
  document.getElementById('sev').value = 3;
  document.getElementById('sev-val').textContent = '3';
  document.getElementById('btn-submit').disabled = true;
}

function setStatus(msg) {
  document.getElementById('status-box').textContent = msg;
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadUsers();
