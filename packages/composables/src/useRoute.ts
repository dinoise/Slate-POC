/**
 * useRoute — route fetching and Leaflet rendering utilities.
 *
 * Port of route-utils.js from adjuster-optimizer to typed TypeScript.
 * Handles Google encoded polyline decoding, ant-path animation,
 * traffic-coloured segment rendering, and the API fetch.
 */

import type * as L from 'leaflet'
import { getAuthToken } from '@slate/api-client'
// leaflet is a peer dependency — loaded by the consuming app at runtime


export interface RouteResult {
  coords: [number, number][]
  traffic_segments: TrafficSegment[]
  duration_s: number | null
  distance_m: number | null
}

export interface TrafficSegment {
  start_index: number
  end_index: number
  speed: 'NORMAL' | 'SLOW' | 'TRAFFIC_JAM'
}

const ROUTE_COLORS = ['#22c55e', '#f59e0b', '#a855f7', '#06b6d4', '#f43f5e']
const TRAFFIC_COLORS: Record<string, string> = {
  NORMAL: '#22c55e',
  SLOW: '#f59e0b',
  TRAFFIC_JAM: '#ef4444',
}

/** Decode a Google-encoded polyline string into [[lat, lon], ...] pairs. */
export function decodePolyline(encoded: string): [number, number][] {
  const coords: [number, number][] = []
  let index = 0
  let lat = 0
  let lng = 0

  while (index < encoded.length) {
    let b: number
    let shift = 0
    let result = 0
    do {
      b = encoded.charCodeAt(index++) - 63
      result |= (b & 0x1f) << shift
      shift += 5
    } while (b >= 32)
    lat += result & 1 ? ~(result >> 1) : result >> 1

    shift = 0
    result = 0
    do {
      b = encoded.charCodeAt(index++) - 63
      result |= (b & 0x1f) << shift
      shift += 5
    } while (b >= 32)
    lng += result & 1 ? ~(result >> 1) : result >> 1

    coords.push([lat / 1e5, lng / 1e5])
  }
  return coords
}

/**
 * Build the winner route layer.
 * Uses ant-path animation when no traffic segments; solid coloured
 * segments when traffic data is present.
 *
 * Requires Leaflet and leaflet-ant-path to be loaded.
 */
function buildRouteLayer(
  L: typeof import('leaflet'),
  coords: [number, number][],
  segments: TrafficSegment[],
  colorIndex: number,
): L.Layer {
  const color = ROUTE_COLORS[colorIndex % ROUTE_COLORS.length]

  if (!segments || segments.length === 0) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return (L.polyline as any).antPath(coords, {
      delay: 800,
      dashArray: [10, 20],
      weight: 5,
      color,
      pulseColor: '#ffffff',
      opacity: 0.9,
    })
  }

  const group = L.layerGroup()
  for (const seg of segments) {
    const slice = coords.slice(seg.start_index, seg.end_index + 1)
    if (slice.length < 2) continue
    L.polyline(slice, {
      color: TRAFFIC_COLORS[seg.speed] ?? '#94a3b8',
      weight: 5,
      opacity: 0.9,
    }).addTo(group)
  }
  return group
}

/** Remove a route layer (ant-path or LayerGroup) from the map safely. */
function removeRouteLayer(map: L.Map, layer: L.Layer | null): void {
  if (!layer) return
  try {
    map.removeLayer(layer)
  } catch {
    // already removed
  }
  // LayerGroup (traffic mode): remove each child too
  if ('eachLayer' in layer) {
    ;(layer as L.LayerGroup).eachLayer((child: L.Layer) => {
      try {
        map.removeLayer(child)
      } catch {
        // ignore
      }
    })
  }
}

/** Fetch a route from the API. Does NOT add anything to the map. */
async function fetchRoute(
  originLat: number,
  originLon: number,
  destLat: number,
  destLon: number,
): Promise<RouteResult> {
  const baseUrl =
    (import.meta as ImportMeta & { env: { VITE_API_BASE_URL?: string } }).env
      .VITE_API_BASE_URL ?? ''

  const params = new URLSearchParams({
    origin_lat: String(originLat),
    origin_lon: String(originLon),
    destination_lat: String(destLat),
    destination_lon: String(destLon),
  })
  const headers: Record<string, string> = {}
  const token = getAuthToken()
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${baseUrl}/api/v1/assignments/route?${params}`, { headers })
  if (!res.ok) throw new Error(`Route API ${res.status}`)

  const data = await res.json()
  if (!data.polyline) throw new Error('No polyline in response')

  return {
    coords: decodePolyline(data.polyline),
    traffic_segments: data.traffic_segments ?? [],
    duration_s: data.duration_s ?? null,
    distance_m: data.distance_m ?? null,
  }
}

/**
 * Build a RouteResult directly from a polyline string already embedded in an
 * SSE payload — skips the round-trip to the route API.
 *
 * When the SSE payload includes traffic segments (populated by a
 * traffic-aware provider such as Google Routes), they are passed through
 * so buildRouteLayer can colour the route. Otherwise falls back to [].
 */
function routeFromPayload(
  polyline: string,
  distanceM: number | null,
  durationS: number | null,
  trafficSegments?: TrafficSegment[] | null,
): RouteResult {
  return {
    coords: decodePolyline(polyline),
    traffic_segments: trafficSegments ?? [],
    distance_m: distanceM,
    duration_s: durationS,
  }
}

export function useRoute() {
  return { decodePolyline, buildRouteLayer, removeRouteLayer, fetchRoute, routeFromPayload }
}
