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
import type {
  AssignmentEvent,
  DemandPrediction,
  FreeAdjuster,
  LayerName,
  ObservatoryClickedFeature,
  RecommendationItem,
} from '@slate/types'
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

// Free adjuster colour (available, no active assignment)
const FREE_ADJ_COLOR: [number, number, number, number] = [156, 163, 175, 200]   // gray-400

// Recommendation colours
const REC_ORIGIN_COLOR:      [number, number, number, number] = [245, 158,  11, 220]  // amber-500 — current pos
const REC_DESTINATION_COLOR: [number, number, number, number] = [ 34, 197,  94, 255]  // green-500 — target pos
const REC_ARROW_COLOR:       [number, number, number, number] = [245, 158,  11, 140]  // amber, semi-transparent

// CDMX default view
const INITIAL_VIEW = { longitude: -99.13, latitude: 19.43, zoom: 10 }

/** Tooltip data exposed to the parent component for overlay rendering.
 *  Discriminated union so the view renders the correct content per marker type. */
export type MapTooltip =
  | { type: 'assignment';    x: number; y: number; event: AssignmentEvent }
  | { type: 'free_adjuster'; x: number; y: number; adjuster: FreeAdjuster }
  | { type: 'demand_hex';    x: number; y: number; prediction: DemandPrediction }

export interface UseObservatoryMapReturn {
  clickedFeature:  Ref<ObservatoryClickedFeature | null>
  layerVisibility: Ref<Record<LayerName, boolean>>
  /** Currently hovered assignment tooltip — null when no marker is hovered. */
  hoveredTooltip:  Ref<MapTooltip | null>
  /** Initialise the map without setting data. Call from onMounted after nextTick. */
  ensureInit:               () => Promise<void>
  setDemandLayer:           (predictions: DemandPrediction[]) => Promise<void>
  setAssignmentsLayer:      (events: AssignmentEvent[])       => Promise<void>
  setFreeAdjustersLayer:    (adjusters: FreeAdjuster[])       => Promise<void>
  /** Render origin→destination arrows for optimizer recommendations.
   *  adjusterPositions maps adjuster_id → {lat, lon} of current position. */
  setRecommendationsLayer:  (
    recs: RecommendationItem[],
    adjusterPositions: Map<number, { lat: number; lon: number }>,
  ) => Promise<void>
  clearRecommendationsLayer: () => void
  toggleLayer:              (name: LayerName, visible: boolean) => void
  /** Register a callback fired on moveend/zoomend with the snapped bbox string. */
  onViewportChange:         (cb: (bbox: string) => void) => void
  destroy:                  () => void
}

export function useObservatoryMap(
  containerRef: Ref<HTMLElement | null>,
): UseObservatoryMapReturn {
  const clickedFeature  = ref<ObservatoryClickedFeature | null>(null)
  const hoveredTooltip  = ref<MapTooltip | null>(null)
  const layerVisibility = ref<Record<LayerName, boolean>>({
    demand:          true,
    assignments:     true,
    routes:          true,
    free_adjusters:  true,
    recommendations: true,
  })

  // Data stores updated by public setters
  let demandData:     DemandPrediction[] = []
  let assignmentData: AssignmentEvent[]  = []
  let freeAdjData:    FreeAdjuster[]     = []

  // Recommendation layers need both the rec item and the adjuster's current position
  interface RecWithOrigin extends RecommendationItem {
    origin_lat: number
    origin_lon: number
  }
  let recommendationData: RecWithOrigin[] = []

  // Currently hovered assignment_id — drives paired highlighting across layers.
  // Stored as a plain variable (not ref) because it's mutated inside Deck.gl
  // callbacks and we always follow it with an explicit _render() call.
  let hoveredAssignmentId: number | null = null

  // Currently hovered free adjuster id — drives highlight on the free-adjusters layer.
  let hoveredFreeAdjId: number | null = null

  // Currently hovered H3 hex index — drives highlight on the demand layer.
  let hoveredHexH3Index: string | null = null

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
    hoveredTooltip.value = object ? { type: 'assignment', x, y, event: object } : null
    _render()
  }

  function _onMarkerClick({ object }: { object: AssignmentEvent | null }) {
    if (!object) return
    clickedFeature.value = { type: 'assignment', assignmentEvent: object }
  }

  // ── Lazy init ──────────────────────────────────────────────────────────────

  function _init(): Promise<void> {
    // If already initialised (or in progress), return the existing promise.
    // But if the container wasn't available last time, initPromise was set to
    // a resolved-empty promise — reset it so we retry on the next call.
    if (initPromise) {
      if (mapInstance) return initPromise   // fully initialised
      if (!containerRef.value) return initPromise  // still no container — keep waiting
      initPromise = null  // container now available but map not created — retry
    }
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

    const hid = hoveredHexH3Index

    return new H3HexagonLayer({
      id: 'demand',
      data: demandData,
      getHexagon: (d: DemandPrediction) => d.h3_r8,
      updateTriggers: { getFillColor: hid },
      getFillColor: (d: DemandPrediction) => {
        const base = DEMAND_COLOURS[d.demand_level] ?? FALLBACK_COLOUR
        if (hid === null) return base
        // Hovered hex: full opacity. All others: dimmed.
        return d.h3_r8 === hid
          ? ([base[0], base[1], base[2], 255] as [number, number, number, number])
          : ([base[0], base[1], base[2],  80] as [number, number, number, number])
      },
      getElevation: 0,
      extruded:     false,
      pickable:     true,
      onHover: ({ object, x, y }: { object: DemandPrediction | null; x: number; y: number }) => {
        if (mapInstance) {
          mapInstance.getCanvas().style.cursor = object ? 'pointer' : ''
        }
        const newId = object?.h3_r8 ?? null
        if (newId === hoveredHexH3Index) return   // no change — skip re-render
        hoveredHexH3Index = newId
        hoveredTooltip.value = object
          ? { type: 'demand_hex', x, y, prediction: object }
          : null
        _render()
      },
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

    const hid    = hoveredAssignmentId
    // Dim assignments entirely when a free adjuster is being hovered
    const dimAll = hoveredFreeAdjId !== null

    return new ScatterplotLayer({
      id:   'incidents',
      data: assignmentData,
      updateTriggers: { getFillColor: hid, getRadius: hid, getLineWidth: hid, _dimAll: dimAll },

      getPosition: (e: AssignmentEvent) => [e.incident.longitude, e.incident.latitude],

      getRadius: (e: AssignmentEvent) => {
        if (dimAll) return 7
        if (hid === null) return 8
        return e.assignment_id === hid ? 11 : 7
      },
      radiusUnits:    'pixels',
      radiusMinPixels: 4,
      radiusMaxPixels: 22,

      getFillColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (dimAll) return [239, 68, 68, 50]
        if (hid === null) return [239, 68, 68, 220]
        return e.assignment_id === hid
          ? [239,  68,  68, 255]
          : [239,  68,  68,  70]
      },

      getLineColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (dimAll) return [255, 255, 255, 30]
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

  function _adjusterLayer() {
    if (!layerVisibility.value.assignments || !ScatterplotLayer) return null
    const withPos = assignmentData.filter((e) => e.adjuster != null)
    if (!withPos.length) return null

    const hid    = hoveredAssignmentId
    const dimAll = hoveredFreeAdjId !== null

    return new ScatterplotLayer({
      id:   'adjusters',
      data: withPos,
      updateTriggers: { getFillColor: hid, getRadius: hid, getLineWidth: hid, _dimAll: dimAll },

      getPosition: (e: AssignmentEvent) => [e.adjuster!.longitude, e.adjuster!.latitude],

      getRadius: (e: AssignmentEvent) => {
        if (dimAll) return 6
        if (hid === null) return 7
        return e.assignment_id === hid ? 10 : 6
      },
      radiusUnits:    'pixels',
      radiusMinPixels: 4,
      radiusMaxPixels: 20,

      getFillColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (dimAll) return [99, 102, 241, 50]
        if (hid === null) return [99, 102, 241, 230]
        return e.assignment_id === hid
          ? [99, 102, 241, 255]
          : [99, 102, 241,  70]
      },

      getLineColor: (e: AssignmentEvent): [number, number, number, number] => {
        if (dimAll) return [255, 255, 255, 30]
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

  // ── Free adjusters layer ──────────────────────────────────────────────────

  function _freeAdjustersLayer() {
    if (!layerVisibility.value.free_adjusters || !ScatterplotLayer) return null
    if (!freeAdjData.length) return null

    const hid = hoveredFreeAdjId

    return new ScatterplotLayer({
      id:   'free-adjusters',
      data: freeAdjData,
      updateTriggers: { getFillColor: hid, getRadius: hid, getLineWidth: hid },

      getPosition: (a: FreeAdjuster) => [a.longitude, a.latitude],

      getRadius: (a: FreeAdjuster) => {
        if (hid === null) return 6
        return a.id === hid ? 9 : 5   // hovered: bigger, others: slightly smaller
      },
      radiusUnits:     'pixels',
      radiusMinPixels: 4,
      radiusMaxPixels: 18,

      getFillColor: (a: FreeAdjuster): [number, number, number, number] => {
        if (hid === null) return FREE_ADJ_COLOR
        return a.id === hid
          ? [209, 213, 219, 255]   // gray-300, full brightness on hover
          : [156, 163, 175,  60]   // gray-400, heavily dimmed
      },

      getLineColor: (a: FreeAdjuster): [number, number, number, number] => {
        if (hid === null) return [255, 255, 255, 160]
        return a.id === hid
          ? [255, 255, 255, 255]   // crisp white ring on hover
          : [255, 255, 255,  40]
      },
      getLineWidth: (a: FreeAdjuster) => (hid !== null && a.id === hid ? 2.5 : 1.5),

      stroked:        true,
      lineWidthUnits: 'pixels',
      pickable:       true,

      onHover: ({ object, x, y }: { object: FreeAdjuster | null; x: number; y: number }) => {
        if (mapInstance) {
          mapInstance.getCanvas().style.cursor = object ? 'pointer' : ''
        }
        const newId = object?.id ?? null
        if (newId === hoveredFreeAdjId) return   // no change — skip re-render

        hoveredFreeAdjId = newId
        hoveredTooltip.value = object
          ? { type: 'free_adjuster', x, y, adjuster: object }
          : null
        _render()
      },

      onClick: ({ object }: { object: FreeAdjuster | null }) => {
        if (!object) return
        clickedFeature.value = { type: 'free_adjuster', freeAdjuster: object }
      },
    })
  }

  // ── Recommendations layers (origin dot + destination dot + arrow) ─────────

  /**
   * Three-layer recommendation visualization (bottom → top):
   *   rec-arrows       : dashed PathLayer ámbar, origin → destination
   *   rec-origin       : ScatterplotLayer ámbar — current adjuster position
   *   rec-destination  : ScatterplotLayer green — recommended hex centroid
   *
   * Destination dots are larger and fully opaque so they read as "where to go".
   * Origin dots are smaller and semi-transparent so they read as "where now".
   * Dashed arrows connect them without adding visual clutter.
   */
  function _recommendationsLayers(): (unknown | null)[] {
    if (!layerVisibility.value.recommendations || !ScatterplotLayer || !PathLayer) return [null]
    if (!recommendationData.length) return [null]

    const arrowLayer = new PathLayer({
      id:   'rec-arrows',
      data: recommendationData,
      getPath:    (r: RecWithOrigin) => [[r.origin_lon, r.origin_lat], [r.recommended_lon, r.recommended_lat]],
      getColor:   REC_ARROW_COLOR,
      getWidth:   2,
      widthUnits: 'pixels',
      getDashArray: [5, 4],
      dashJustified: true,
      pickable:   false,
    })

    const originLayer = new ScatterplotLayer({
      id:   'rec-origin',
      data: recommendationData,
      getPosition:  (r: RecWithOrigin) => [r.origin_lon, r.origin_lat],
      getRadius:        7,
      radiusUnits:      'pixels',
      radiusMinPixels:  4,
      radiusMaxPixels:  16,
      getFillColor:     REC_ORIGIN_COLOR,
      getLineColor:     [255, 255, 255, 200] as [number, number, number, number],
      getLineWidth:     1.5,
      stroked:          true,
      lineWidthUnits:   'pixels',
      pickable:         false,
    })

    const destLayer = new ScatterplotLayer({
      id:   'rec-destination',
      data: recommendationData,
      getPosition:  (r: RecWithOrigin) => [r.recommended_lon, r.recommended_lat],
      getRadius:        10,
      radiusUnits:      'pixels',
      radiusMinPixels:  6,
      radiusMaxPixels:  22,
      getFillColor:     REC_DESTINATION_COLOR,
      getLineColor:     [255, 255, 255, 255] as [number, number, number, number],
      getLineWidth:     2,
      stroked:          true,
      lineWidthUnits:   'pixels',
      pickable:         true,
      onClick: ({ object }: { object: RecWithOrigin | null }) => {
        if (!object) return
        clickedFeature.value = { type: 'recommendation', recommendation: object }
      },
      onHover: ({ object }: { object: RecWithOrigin | null }) => {
        if (mapInstance) {
          mapInstance.getCanvas().style.cursor = object ? 'pointer' : ''
        }
      },
    })

    return [arrowLayer, originLayer, destLayer]
  }

  // ── Re-render ─────────────────────────────────────────────────────────────

  function _render() {
    if (!deckOverlay) return
    deckOverlay.setProps({
      layers: [
        _demandLayer(),
        ..._routesLayers(),           // routes below markers
        ..._recommendationsLayers(),  // recommendations above demand, below live markers
        _freeAdjustersLayer(),        // available adjusters (gray)
        _incidentLayer(),
        _adjusterLayer(),             // assigned adjusters always on top
      ].filter(Boolean),
    })
  }

  // ── Public API ────────────────────────────────────────────────────────────

  /** Explicitly initialise the map without setting any data.
   *  Call this from onMounted (after nextTick) so the map exists before
   *  any parallel data loaders call their set*Layer methods. */
  async function ensureInit() {
    await _init()
  }

  async function setDemandLayer(predictions: DemandPrediction[]) {
    await _init()
    demandData = [...predictions]   // unwrap Vue proxy → plain array for Deck.gl
    _render()
  }

  async function setAssignmentsLayer(events: AssignmentEvent[]) {
    await _init()
    assignmentData = [...events]
    _render()
  }

  async function setFreeAdjustersLayer(adjusters: FreeAdjuster[]) {
    await _init()
    freeAdjData = [...adjusters]
    _render()
  }

  async function setRecommendationsLayer(
    recs: RecommendationItem[],
    adjusterPositions: Map<number, { lat: number; lon: number }>,
  ) {
    await _init()
    recommendationData = recs.map((r) => {
      const origin = adjusterPositions.get(r.adjuster_id)
      return {
        ...r,
        // Fall back to destination if adjuster position unknown (shouldn't happen)
        origin_lat: origin?.lat ?? r.recommended_lat,
        origin_lon: origin?.lon ?? r.recommended_lon,
      }
    })
    _render()
  }

  function clearRecommendationsLayer() {
    recommendationData = []
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
    ensureInit,
    setDemandLayer,
    setAssignmentsLayer,
    setFreeAdjustersLayer,
    setRecommendationsLayer,
    clearRecommendationsLayer,
    toggleLayer,
    onViewportChange,
    destroy,
  }
}
