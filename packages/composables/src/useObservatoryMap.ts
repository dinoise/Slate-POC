/**
 * useObservatoryMap — Deck.gl + MapLibre map for the admin observatory.
 *
 * Manages four Deck.gl layers rendered over a MapLibre GL base map:
 *   - H3HexagonLayer  : demand predictions coloured by intensity
 *   - ScatterplotLayer: active incident positions (from SSE events)
 *   - ScatterplotLayer: adjuster home positions (from SSE events)
 *   - PathLayer       : active routes decoded from assignment polylines
 *
 * Hover interactions (paired highlighting):
 *   Hovering any marker (incident or adjuster) highlights all three linked
 *   objects — incident dot, adjuster dot, and connecting route — while
 *   dimming unrelated routes. A tooltip with assignment info is also exposed.
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

// Route colours
const ROUTE_BASE_COLOR:  [number, number, number, number] = [99,  102, 241, 140]  // indigo, dimmed
const ROUTE_HOVER_COLOR: [number, number, number, number] = [245, 158,  11, 255]  // amber-500, full opacity

// CDMX default view
const INITIAL_VIEW = { longitude: -99.13, latitude: 19.43, zoom: 10 }

/** Tooltip data exposed to the parent component for overlay rendering. */
export interface MapTooltip {
  /** Canvas x/y pixel coordinates from Deck.gl pickingInfo. */
  x: number
  y: number
  event: AssignmentEvent
}

export interface UseObservatoryMapReturn {
  clickedFeature:  Ref<ObservatoryClickedFeature | null>
  layerVisibility: Ref<Record<LayerName, boolean>>
  /** Currently hovered assignment tooltip — null when no marker is hovered. */
  hoveredTooltip:  Ref<MapTooltip | null>
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
  const clickedFeature  = ref<ObservatoryClickedFeature | null>(null)
  const hoveredTooltip  = ref<MapTooltip | null>(null)
  const layerVisibility = ref<Record<LayerName, boolean>>({
    demand:      true,
    assignments: true,
    routes:      true,
  })

  // Data stores updated by public setters
  let demandData:     DemandPrediction[] = []
  let assignmentData: AssignmentEvent[]  = []

  // Currently hovered assignment_id — drives paired highlighting across layers.
  // Stored as a plain variable (not ref) because it's mutated inside Deck.gl
  // callbacks and we always follow it with an explicit _render() call.
  let hoveredAssignmentId: number | null = null

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

  // ── Hover handlers shared by incident, adjuster, and route layers ────────

  function _onMarkerHover({ object, x, y }: { object: AssignmentEvent | null; x: number; y: number }) {
    const newId = object?.assignment_id ?? null

    // Set cursor directly on the MapLibre canvas element.
    // MapLibre overrides the CSS cursor with its own grab/grabbing styles, so
    // mutating getCursor on the MapboxOverlay is not reliable — direct DOM
    // mutation on the canvas wins the CSS specificity race.
    if (mapInstance) {
      mapInstance.getCanvas().style.cursor = object ? 'pointer' : ''
    }

    if (newId === hoveredAssignmentId) return   // no change — skip re-render

    hoveredAssignmentId = newId
    hoveredTooltip.value = object ? { x, y, event: object } : null
    _render()
  }

  function _onMarkerClick({ object }: { object: AssignmentEvent | null }) {
    if (!object) return
    clickedFeature.value = { type: 'assignment', assignmentEvent: object }
  }

  // ── Lazy init ──────────────────────────────────────────────────────────────

  function _init(): Promise<void> {
    if (initPromise) return initPromise
    initPromise = (async () => {
      if (!containerRef.value) return

      const maplibre   = await import('maplibre-gl')
      const deckMapbox = await import('@deck.gl/mapbox')
      const geoLayers  = await import('@deck.gl/geo-layers')
      const layers     = await import('@deck.gl/layers')

      const { Map } = maplibre
      const { MapboxOverlay } = deckMapbox

      H3HexagonLayer   = geoLayers.H3HexagonLayer
      ScatterplotLayer = layers.ScatterplotLayer
      PathLayer        = layers.PathLayer

      mapInstance = new Map({
        container: containerRef.value!,
        // OpenFreeMap Positron — free, reliable, no API key required
        style: 'https://tiles.openfreemap.org/styles/positron',
        center: [INITIAL_VIEW.longitude, INITIAL_VIEW.latitude],
        zoom:   INITIAL_VIEW.zoom,
      })

      deckOverlay = new MapboxOverlay({
        interleaved: false,
        layers: [],
        getCursor: ({ isHovering, isDragging }: { isHovering: boolean; isDragging: boolean }) => {
          if (isDragging) return 'grabbing'
          if (isHovering) return 'pointer'
          return 'grab'
        },
      })
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

  /**
   * Marker getFillColor / getRadius with hover-aware paired highlighting.
   *
   * When something is hovered:
   *   - The hovered assignment's markers are brightened + enlarged.
   *   - All other assignment markers are dimmed to 60 alpha.
   * When nothing is hovered every marker uses its base style.
   */
  function _incidentLayer() {
    if (!layerVisibility.value.assignments || !ScatterplotLayer) return null

    const hid = hoveredAssignmentId

    return new ScatterplotLayer({
      id:   'incidents',
      data: assignmentData,
      // Key on hovered id so Deck.gl recomputes per-object accessors when it changes
      updateTriggers: { getFillColor: hid, getRadius: hid, getLineWidth: hid },

      getPosition: (e: AssignmentEvent) => [e.incident.longitude, e.incident.latitude],

      getRadius: (e: AssignmentEvent) => {
        if (hid === null) return 8
        return e.assignment_id === hid ? 11 : 7   // hovered: +37%, others: slightly smaller
      },
      radiusUnits:    'pixels',
      radiusMinPixels: 4,
      radiusMaxPixels: 22,

      getFillColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (hid === null) return [239, 68, 68, 220]
        return e.assignment_id === hid
          ? [239,  68,  68, 255]   // full brightness
          : [239,  68,  68,  70]   // dimmed
      },

      getLineColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (hid === null) return [255, 255, 255, 200]
        return e.assignment_id === hid
          ? [255, 255, 255, 255]   // crisp white ring on hover
          : [255, 255, 255,  60]
      },
      getLineWidth: (e: AssignmentEvent) => (hid !== null && e.assignment_id === hid ? 2.5 : 1.5),

      stroked:        true,
      lineWidthUnits: 'pixels',
      pickable:       true,

      onHover: _onMarkerHover,
      onClick: _onMarkerClick,
    })
  }

  function _adjusterLayer() {
    if (!layerVisibility.value.assignments || !ScatterplotLayer) return null
    const withPos = assignmentData.filter((e) => e.adjuster != null)
    if (!withPos.length) return null

    const hid = hoveredAssignmentId

    return new ScatterplotLayer({
      id:   'adjusters',
      data: withPos,
      updateTriggers: { getFillColor: hid, getRadius: hid, getLineWidth: hid },

      getPosition: (e: AssignmentEvent) => [e.adjuster!.longitude, e.adjuster!.latitude],

      getRadius: (e: AssignmentEvent) => {
        if (hid === null) return 7
        return e.assignment_id === hid ? 10 : 6
      },
      radiusUnits:    'pixels',
      radiusMinPixels: 4,
      radiusMaxPixels: 20,

      getFillColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (hid === null) return [99, 102, 241, 230]
        return e.assignment_id === hid
          ? [99, 102, 241, 255]
          : [99, 102, 241,  70]
      },

      getLineColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (hid === null) return [255, 255, 255, 200]
        return e.assignment_id === hid
          ? [255, 255, 255, 255]
          : [255, 255, 255,  60]
      },
      getLineWidth: (e: AssignmentEvent) => (hid !== null && e.assignment_id === hid ? 2.5 : 1.5),

      stroked:        true,
      lineWidthUnits: 'pixels',
      pickable:       true,

      onHover: _onMarkerHover,
      onClick: _onMarkerClick,
    })
  }

  /**
   * Routes are split into three PathLayer passes (bottom → top):
   *
   *   routes-base     — all routes, visible, dimmed when a hover is active.
   *                     pickable: true — fires onHover/onClick for the tooltip.
   *   routes-hover    — only the hovered route, amber + wider. pickable: false
   *                     (visual only; base layer already owns the pick event).
   *   routes-hit-area — invisible wide strip (16 px) covering all routes.
   *                     pickable: true, always present, makes thin lines easy
   *                     to hover — same industry pattern as Mapbox/Google Maps
   *                     "click area" layers.
   *
   * Only routes-base and routes-hit-area are pickable to avoid double-firing.
   */
  function _routesLayers(): (unknown | null)[] {
    if (!layerVisibility.value.routes || !PathLayer) return [null]
    const withRoute = assignmentData.filter((e) => e.route?.polyline)
    if (!withRoute.length) return [null]

    const hid      = hoveredAssignmentId
    const hasHover = hid !== null

    const getPath = (e: AssignmentEvent) =>
      decodePolyline(e.route!.polyline!).map(([lat, lon]) => [lon, lat])

    // ── Base layer (visible, pickable) ───────────────────────────────────────
    const baseColor: [number, number, number, number] = [
      ROUTE_BASE_COLOR[0], ROUTE_BASE_COLOR[1], ROUTE_BASE_COLOR[2],
      Math.round(ROUTE_BASE_COLOR[3] * (hasHover ? 0.28 : 1)),
    ]

    const baseLayer = new PathLayer({
      id:   'routes-base',
      data: withRoute,
      updateTriggers: { getColor: hasHover },
      getPath,
      getColor:   baseColor,
      getWidth:   3,
      widthUnits: 'pixels',
      pickable:   true,
      opacity:    hasHover ? 0.25 : 0.78,
      onHover: _onMarkerHover,
      onClick: _onMarkerClick,
    })

    // ── Hit area layer (invisible, wide, always on top of base) ──────────────
    // 16 px transparent strip — makes thin lines easy to hover/click.
    // Uses opacity:0 getColor trick; Deck.gl still picks against the geometry.
    const hitLayer = new PathLayer({
      id:   'routes-hit-area',
      data: withRoute,
      getPath,
      getColor:   [0, 0, 0, 0] as [number, number, number, number],
      getWidth:   16,
      widthUnits: 'pixels',
      pickable:   true,
      onHover: _onMarkerHover,
      onClick: _onMarkerClick,
    })

    if (!hasHover) return [baseLayer, hitLayer]

    // ── Hover highlight layer (visual only, not pickable) ────────────────────
    const hoveredRoutes = withRoute.filter((e) => e.assignment_id === hid)
    if (!hoveredRoutes.length) return [baseLayer, hitLayer]

    const hoverLayer = new PathLayer({
      id:   'routes-hover',
      data: hoveredRoutes,
      getPath,
      getColor:   ROUTE_HOVER_COLOR,
      getWidth:   7,
      widthUnits: 'pixels',
      pickable:   false,
    })

    // Order: base → hover highlight → hit area (hit area must be topmost to intercept mouse)
    return [baseLayer, hoverLayer, hitLayer]
  }

  // ── Re-render ─────────────────────────────────────────────────────────────

  function _render() {
    if (!deckOverlay) return
    deckOverlay.setProps({
      layers: [
        _demandLayer(),
        ..._routesLayers(),   // routes drawn below markers so markers are always on top
        _incidentLayer(),
        _adjusterLayer(),
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

  return {
    clickedFeature,
    hoveredTooltip,
    layerVisibility,
    setDemandLayer,
    setAssignmentsLayer,
    toggleLayer,
    onViewportChange,
    destroy,
  }
}
