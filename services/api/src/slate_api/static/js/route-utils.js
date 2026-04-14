'use strict';
// ── Shared route-rendering utilities ─────────────────────────────────────────
// Used by both map.js (optimizer view) and adjuster.js (adjuster view).
// Depends on Leaflet and leaflet-ant-path being loaded before this script.

const ROUTE_COLORS = ['#22c55e', '#f59e0b', '#a855f7', '#06b6d4', '#f43f5e'];
const TRAFFIC_COLORS = { NORMAL: '#22c55e', SLOW: '#f59e0b', TRAFFIC_JAM: '#ef4444' };

/**
 * Decode a Google-encoded polyline string into [[lat, lon], ...] pairs.
 * Used as fallback when the Leaflet.encoded plugin is not loaded.
 */
function decodePolyline(encoded) {
  const coords = [];
  let index = 0, lat = 0, lng = 0;
  while (index < encoded.length) {
    let b, shift = 0, result = 0;
    do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 32);
    lat += (result & 1) ? ~(result >> 1) : (result >> 1);
    shift = 0; result = 0;
    do { b = encoded.charCodeAt(index++) - 63; result |= (b & 0x1f) << shift; shift += 5; } while (b >= 32);
    lng += (result & 1) ? ~(result >> 1) : (result >> 1);
    coords.push([lat / 1e5, lng / 1e5]);
  }
  return coords;
}

/**
 * Decode a route polyline from an API response object.
 * Prefers L.PolylineUtil (Leaflet.encoded plugin) when available.
 */
function decodeRoutePolyline(polyline) {
  return typeof L.PolylineUtil !== 'undefined'
    ? L.PolylineUtil.decode(polyline, 5)
    : decodePolyline(polyline);
}

/**
 * Build the winner route layer: antPath when no traffic, segmented solid
 * polylines when traffic data is present.
 *
 * @param {Array} coords   [[lat, lon], ...]
 * @param {Array} segments traffic_segments array from the API
 * @param {string} color   hex color for the antPath fallback
 * @returns {L.Layer}
 */
function buildRouteLayer(coords, segments, color) {
  if (!segments || segments.length === 0) {
    return L.polyline.antPath(coords, {
      delay: 800, dashArray: [10, 20], weight: 5,
      color, pulseColor: '#ffffff', opacity: 0.9,
    });
  }

  // Traffic mode: one solid polyline per segment, grouped so it can be
  // removed as a single unit with map.removeLayer(group).
  const group = L.layerGroup();
  for (const seg of segments) {
    const slice = coords.slice(seg.start_index, seg.end_index + 1);
    if (slice.length < 2) continue;
    L.polyline(slice, {
      color: TRAFFIC_COLORS[seg.speed] ?? '#94a3b8',
      weight: 5,
      opacity: 0.9,
      lineJoin: 'round',
    }).addTo(group);
  }
  return group;
}

/**
 * Build a dashed candidate (non-winner) route layer with optional traffic
 * coloring.
 *
 * @param {Array} coords   [[lat, lon], ...]
 * @param {Array} segments traffic_segments array from the API
 * @returns {L.Layer}
 */
function buildCandidateLayer(coords, segments) {
  if (!segments || segments.length === 0) {
    return L.polyline(coords, { color: '#94a3b8', weight: 2.5, dashArray: '6 8', opacity: 0.75 });
  }

  const group = L.layerGroup();
  for (const seg of segments) {
    const slice = coords.slice(seg.start_index, seg.end_index + 1);
    if (slice.length < 2) continue;
    L.polyline(slice, {
      color: TRAFFIC_COLORS[seg.speed] ?? '#94a3b8',
      weight: 3,
      opacity: 0.7,
      dashArray: '6 8',
    }).addTo(group);
  }
  return group;
}

/**
 * Remove a route layer (antPath or LayerGroup) from the map safely.
 * Handles both plain polylines and L.layerGroup (traffic-coloured segments).
 *
 * @param {L.Map} map
 * @param {L.Layer} layer
 */
function removeRouteLayer(map, layer) {
  if (!layer) return;
  try { map.removeLayer(layer); } catch (_) {}
  // LayerGroup (traffic mode): also remove each child from the map directly
  if (layer.eachLayer) {
    layer.eachLayer(child => { try { map.removeLayer(child); } catch (_) {} });
  }
}

/**
 * Fetch a route from the API and return { coords, traffic_segments } or null
 * on error. Does NOT add anything to the map.
 *
 * @param {number} originLat
 * @param {number} originLon
 * @param {number} destLat
 * @param {number} destLon
 * @returns {Promise<{coords: Array, traffic_segments: Array}|null>}
 */
async function fetchRoute(originLat, originLon, destLat, destLon) {
  const params = new URLSearchParams({
    origin_lat: originLat, origin_lon: originLon,
    destination_lat: destLat, destination_lon: destLon,
  });
  const res = await fetch(`/api/v1/assignments/route?${params}`);
  if (!res.ok) throw new Error(`Route API ${res.status}`);
  const data = await res.json();
  if (!data.polyline) throw new Error('No polyline in response');
  return {
    coords: decodeRoutePolyline(data.polyline),
    traffic_segments: data.traffic_segments ?? [],
    duration_s: data.duration_s,
    distance_m: data.distance_m,
  };
}
