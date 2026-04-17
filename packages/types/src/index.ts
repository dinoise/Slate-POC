// ── Enums ─────────────────────────────────────────────────────────────────────

export type IncidentType =
  | 'collision'
  | 'theft'
  | 'fire'
  | 'flood'
  | 'vandalism'
  | 'other'

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical'

export type AdjusterStatus = 'available' | 'busy' | 'offline'

export type AssignmentStatus =
  | 'assigned'
  | 'accepted'
  | 'en_route'
  | 'arrived'
  | 'completed'
  | 'cancelled'

export type RouteProvider = 'osrm' | 'valhalla' | 'google'

// ── Models ────────────────────────────────────────────────────────────────────

export interface Incident {
  id: number
  incident_type: IncidentType
  severity: SeverityLevel
  description: string
  address: string
  latitude: number
  longitude: number
  status: string
  reporter_name: string
  reporter_email: string
  created_at: string
  updated_at: string
}

export interface Adjuster {
  id: number
  name: string
  email: string
  phone: string
  status: AdjusterStatus
  specializations: IncidentType[]
  latitude: number | null
  longitude: number | null
  created_at: string
  updated_at: string
}

export interface Assignment {
  id: number
  incident_id: number
  adjuster_id: number
  status: AssignmentStatus
  distance_km: number | null
  travel_time_minutes: number | null
  assigned_at: string
  accepted_at: string | null
  completed_at: string | null
  notes: string | null
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

// ── SSE Events ────────────────────────────────────────────────────────────────

export interface AssignmentEvent {
  assignment_id: number
  adjuster_id: number
  incident_id: number
  incident_type: IncidentType
  severity: SeverityLevel
  description: string
  address: string
  latitude: number
  longitude: number
  distance_km: number | null
  travel_time_minutes: number | null
  status: AssignmentStatus
  assigned_at: string
}

// ── Settings ──────────────────────────────────────────────────────────────────

export interface ProviderSettings {
  provider: RouteProvider
}
