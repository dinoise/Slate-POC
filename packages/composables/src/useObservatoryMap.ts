/**
 * useObservatoryMap — Deck.gl + MapLibre map for the admin observatory.
 *
 * Manages three Deck.gl layers rendered over a MapLibre GL base map:
 *   - H3HexagonLayer  : demand predictions coloured by intensity
 *   - ScatterplotLayer: active incident positions (from SSE events)
 *   - PathLayer       : active routes decoded from assignment polylines
 *
 * Callers update data via `setDemandLayer` / `setAssignmentsLayer`.
 * Layer visibility is controlled via `toggleLayer`.
 * Click interactions set `clickedFeature` for the parent side drawer.
 */

import { ref, onUnmounted, type Ref } from 'vue'
import type { AssignmentEvent, DemandPrediction, LayerName, ObservatoryClickedFeature } from '@slate/types'
import { decodePolyline } from './useRoute'

// ── Demand colour scale (demand_level 0=low 1=med 2=high) ─────────────────────
const DEMAND_COLOURS: Record<number, [number, number, number, number]> = {
  0: [59,  130, 246, 160],   // blue-500   — low
  1: [249, 115,  22, 180],   // orange-500 — medium
  2: [220,  38,  38, 200],   // red-600    — high
}
const FALLBACK_COLOUR: [number, number, number, number] = [156, 163, 175, 100]

// CDMX default view
const INITIAL_VIEW = { longitude: -99.13, latitude: 19.43, zoom: 10 }

export interface UseObservatoryMapReturn {
  clickedFeature:  Ref<ObservatoryClickedFeature | null>
  layerVisibility: Ref<Record<LayerName, boolean>>
  setDemandLayer:      (predictions: DemandPrediction[]) => Promise<void>
  setAssignmentsLayer: (events: AssignmentEvent[])       => Promise<void>
  toggleLayer:         (name: LayerName, visible: boolean) => void
  /** Register a callback fired on moveend/zoomend with the snapped bbox string. */
  onViewportChange:    (cb: (bbox: string) => void) => void
  destroy:             () => void
}

export function useObservatoryMap(
  containerRef: Ref<HTMLElement | null>,
): UseObservatoryMapReturn {
  const clickedFeature = ref<ObservatoryClickedFeature | null>(null)
  const layerVisibility = ref<Record<LayerName, boolean>>({
    demand:      true,
    assignments: true,
    routes:      true,
  })

  // Data stores updated by public setters
  let demandData:     DemandPrediction[] = []
  let assignmentData: AssignmentEvent[]  = []

  // Deck.gl / MapLibre instances — created once on first setter call
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let deckOverlay: any = null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let mapInstance: any = null

  // Layer constructors stored after dynamic import
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let H3HexagonLayer: any  = null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let ScatterplotLayer: any = null
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  let PathLayer: any        = null

  let initPromise: Promise<void> | null = null

  // Viewport change callback — set via onViewportChange()
  let _viewportCallback: ((bbox: string) => void) | null = null

  /** Snap coordinate to 1 decimal (~11km grid) to maximise cache hits. */
  function _snap(n: number): number { return Math.round(n * 10) / 10 }

  /** Current map bounds as "minLat,minLon,maxLat,maxLon" string, snapped. */
  function _currentBbox(): string {
    const b = mapInstance.getBounds()
    return [
      _snap(b.getSouth()),
      _snap(b.getWest()),
      _snap(b.getNorth()),
      _snap(b.getEast()),
    ].join(',')
  }

  // ── Lazy init ──────────────────────────────────────────────────────────────

  function _init(): Promise<void> {
    if (initPromise) return initPromise
    initPromise = (async () => {
      if (!containerRef.value) return

      const maplibre  = await import('maplibre-gl')
      const deckMapbox = await import('@deck.gl/mapbox')
      const geoLayers  = await import('@deck.gl/geo-layers')
      const layers     = await import('@deck.gl/layers')

      const { Map } = maplibre
      const { MapboxOverlay } = deckMapbox

      H3HexagonLayer  = geoLayers.H3HexagonLayer
      ScatterplotLayer = layers.ScatterplotLayer
      PathLayer        = layers.PathLayer

      mapInstance = new Map({
        container: containerRef.value!,
        // OpenFreeMap Positron — free, reliable, no API key required
        style: 'https://tiles.openfreemap.org/styles/positron',
        center: [INITIAL_VIEW.longitude, INITIAL_VIEW.latitude],
        zoom:   INITIAL_VIEW.zoom,
      })

      deckOverlay = new MapboxOverlay({ interleaved: false, layers: [] })
      mapInstance.addControl(deckOverlay)

      // Notify caller on pan/zoom end — use snapped bbox to maximise cache hits
      mapInstance.on('moveend', () => { if (_viewportCallback) _viewportCallback(_currentBbox()) })
      mapInstance.on('zoomend', () => { if (_viewportCallback) _viewportCallback(_currentBbox()) })

      // Render once the base map tiles have loaded.
      // If 'load' already fired (style cached), mapInstance.loaded() is true.
      if (mapInstance.loaded()) {
        _render()
      } else {
        mapInstance.on('load', () => _render())
      }
    })()
    return initPromise
  }

  // ── Layer builders ────────────────────────────────────────────────────────

  function _demandLayer() {
    if (!layerVisibility.value.demand || !H3HexagonLayer) return null
    return new H3HexagonLayer({
      id: 'demand',
      data: demandData,
      getHexagon:   (d: DemandPrediction) => d.h3_r8,
      getFillColor: (d: DemandPrediction) => DEMAND_COLOURS[d.demand_level] ?? FALLBACK_COLOUR,
      getElevation: 0,
      extruded:     false,
      pickable:     true,
      onClick: ({ object }: { object: DemandPrediction | null }) => {
        if (!object) return
        clickedFeature.value = {
          type:        'hexagon',
          h3Index:     object.h3_r8,
          demandLevel: object.demand_level,
          predAbs:     object.pred_abs,
        }
      },
    })
  }

  function _incidentLayer() {
    if (!layerVisibility.value.assignments || !ScatterplotLayer) return null
    return new ScatterplotLayer({
      id:           'incidents',
      data:         assignmentData,
      getPosition:  (e: AssignmentEvent) => [e.longitude, e.latitude],
      getRadius:    400,
      getFillColor: [239, 68, 68, 200],   // red-500
      pickable:     true,
      onClick: ({ object }: { object: AssignmentEvent | null }) => {
        if (!object) return
        clickedFeature.value = { type: 'assignment', assignmentEvent: object }
      },
    })
  }

  function _routesLayer() {
    if (!layerVisibility.value.routes || !PathLayer) return null
    const withRoute = assignmentData.filter((e) => e.route_polyline)
    if (!withRoute.length) return null
    return new PathLayer({
      id:   'routes',
      data: withRoute,
      // decodePolyline returns [lat, lon]; Deck.gl wants [lon, lat]
      getPath:  (e: AssignmentEvent) =>
        decodePolyline(e.route_polyline!).map(([lat, lon]) => [lon, lat]),
      getColor: [99, 102, 241, 200],   // indigo-500
      getWidth: 4,
      widthUnits: 'pixels',
      pickable: false,
    })
  }

  // ── Re-render ─────────────────────────────────────────────────────────────

  function _render() {
    if (!deckOverlay) return
    deckOverlay.setProps({
      layers: [
        _demandLayer(),
        _incidentLayer(),
        _routesLayer(),
      ].filter(Boolean),
    })
  }

  // ── Public API ────────────────────────────────────────────────────────────

  async function setDemandLayer(predictions: DemandPrediction[]) {
    await _init()
    demandData = predictions
    _render()
  }

  async function setAssignmentsLayer(events: AssignmentEvent[]) {
    await _init()
    assignmentData = events
    _render()
  }

  function toggleLayer(name: LayerName, visible: boolean) {
    layerVisibility.value[name] = visible
    _render()
  }

  function onViewportChange(cb: (bbox: string) => void) {
    _viewportCallback = cb
  }

  function destroy() {
    _viewportCallback = null
    deckOverlay?.finalize?.()
    mapInstance?.remove()
    deckOverlay  = null
    mapInstance  = null
    initPromise  = null
  }

  onUnmounted(destroy)

  return { clickedFeature, layerVisibility, setDemandLayer, setAssignmentsLayer, toggleLayer, onViewportChange, destroy }
}
