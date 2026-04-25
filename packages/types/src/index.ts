// ── Enums (re-exported from enums.ts) ────────────────────────────────────────
export {
  IncidentType,
  IncidentStatus,
  AssignmentStatus,
  AdjusterStatus,
  RouteProvider,
  ACTIVE_INCIDENT_STATUSES,
  ACTIVE_ASSIGNMENT_STATUSES,
  TERMINAL_ASSIGNMENT_STATUSES,
  BUSY_ADJUSTER_STATUSES,
} from './enums'
export type { SeverityLevel } from './enums'

// ── Models ────────────────────────────────────────────────────────────────────

import type {
  IncidentType,
  IncidentStatus,
  AssignmentStatus,
  AdjusterStatus,
  SeverityLevel,
  RouteProvider,
} from './enums'

export interface Incident {
  id: number
  external_id: string
  incident_type: IncidentType
  severity: SeverityLevel
  description: string | null
  address: string | null
  latitude: number
  longitude: number
  incident_datetime: string
  reported_by_user_id: number | null
  status: IncidentStatus
  created_at: string
  updated_at: string
}

export interface Adjuster {
  id: number
  external_id: string
  first_name: string
  last_name: string
  email: string
  phone: string | null
  home_latitude: number
  home_longitude: number
  skills: string[]
  max_cases_per_day: number
  is_active: boolean
  status: AdjusterStatus
  current_latitude: number | null
  current_longitude: number | null
  created_at: string
  updated_at: string
}

export interface AdjusterCreate {
  external_id: string
  first_name: string
  last_name: string
  email: string
  phone?: string
  home_latitude: number
  home_longitude: number
  skills: string[]
  max_cases_per_day: number
}

export interface AdjusterUpdate {
  first_name?: string
  last_name?: string
  email?: string
  phone?: string
  skills?: string[]
  max_cases_per_day?: number
  is_active?: boolean
  status?: AdjusterStatus
}

export interface Assignment {
  id: number
  incident_id: number
  adjuster_id: number
  status: AssignmentStatus
  distance_km: number | null
  travel_time_minutes: number | null
  optimization_score: number | null
  assigned_at: string
  estimated_arrival_time: string | null
  actual_arrival_time: string | null
  completed_at: string | null
  notes: string | null
  // Route data — populated after route-fetching job runs
  route_polyline: string | null
  route_provider: string | null
  route_distance_m: number | null
  route_duration_s: number | null
  route_traffic_segments: TrafficSegment[] | null
  created_at: string
  updated_at: string
}

export interface AssignmentStatusHistory {
  id: number
  assignment_id: number
  from_status: AssignmentStatus | null
  to_status: AssignmentStatus
  changed_at: string
  changed_by: string | null
}

export interface AdjusterPosition {
  id: number
  adjuster_id: number
  latitude: number
  longitude: number
  recorded_at: string
}

export interface DemandPrediction {
  id: number
  lat: number
  lon: number
  h3_r8: string
  hora_num: number
  dia_semana_num: number
  pred_ratio: number
  pred_abs: number
  demand_level: number  // 0=Low, 1=Med, 2=High
  model_version: string
  predicted_for: string
  created_at: string
}

export interface DemandSlot {
  dia_semana_num: number
  hora_num: number
}

export interface User {
  id: number
  name: string
  email: string
  role: string
  created_at: string
}

// ── API Responses ─────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ApiError {
  detail: string
}

// ── Route ─────────────────────────────────────────────────────────────────────

export interface TrafficSegment {
  start_index: number
  end_index: number
  speed: 'NORMAL' | 'SLOW' | 'TRAFFIC_JAM'
}

// ── SSE Events ────────────────────────────────────────────────────────────────

export interface IncidentInfo {
  id: number
  type: IncidentType
  severity: SeverityLevel
  description: string | null
  address: string | null
  latitude: number
  longitude: number
}

export interface AdjusterInfo {
  id: number
  /** Home latitude from adjusters table — always present. */
  latitude: number
  /** Home longitude from adjusters table — always present. */
  longitude: number
}

export interface RouteInfo {
  polyline: string | null
  provider: string | null
  distance_m: number | null
  duration_s: number | null
  traffic_segments: TrafficSegment[] | null
}

export interface AssignmentEvent {
  assignment_id: number
  status: AssignmentStatus
  /** Discriminator — 'assignment.created' | 'assignment.updated' */
  event_type?: string
  assigned_at: string
  distance_km: number | null
  travel_time_minutes: number | null
  incident: IncidentInfo
  /** Home position of the assigned adjuster — null on enrichment fallback. */
  adjuster: AdjusterInfo | null
  /** Route data — null until route-fetching job runs. */
  route: RouteInfo | null
}

// ── Observatory ───────────────────────────────────────────────────────────────

/** Names of toggleable map layers in the observatory dashboard. */
export type LayerName = 'demand' | 'assignments' | 'routes'

/** Feature selected by clicking on the observatory map. */
export interface ObservatoryClickedFeature {
  type: 'assignment' | 'hexagon'
  /** Populated when clicking a siniestro/adjuster marker. */
  assignmentEvent?: AssignmentEvent
  /** Populated when clicking an H3 hexagon. */
  h3Index?: string
  demandLevel?: number
  predAbs?: number
}

// ── Settings ──────────────────────────────────────────────────────────────────

export interface ProviderSettings {
  provider: RouteProvider
}

// ── Positioning Recommendations ───────────────────────────────────────────────

export interface RecommendationRequest {
  scenario?: string          // default: "initial"
  hora_num: number           // 0–23
  dia_semana_num: number     // 0=Mon … 6=Sun
  radio_km?: number          // default: 7.5
  umbral_gain?: number       // default: 0.5
  spread_factor?: number     // 0–1, default: 0.5
  spread_rings?: number      // 1–8, default: 3
  save_as_scenario?: string | null
}

export interface RecommendationItem {
  adjuster_id: number
  adjuster_name: string
  current_hex: string | null
  recommended_hex: string
  recommended_lat: number
  recommended_lon: number
  demand_gain: number
  distance_km: number
  eta_min: number
  reason: string
}

export interface RecommendationResponse {
  scenario_source: string
  hora_num: number
  dia_semana_num: number
  total_adjusters: number
  adjusters_to_move: number
  recommendations: RecommendationItem[]
  saved_as: string | null
}
