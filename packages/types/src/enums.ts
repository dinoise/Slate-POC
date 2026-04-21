/**
 * Domain enumerations — mirrors services/api/src/slate_api/core/enums.py
 *
 * Pattern: `const` object (runtime values) + union type (compile-time)
 * with the same name, matching Python's StrEnum behaviour.
 */

// ── IncidentType ──────────────────────────────────────────────────────────────

export const IncidentType = {
  COLLISION: 'collision',
  THEFT:     'theft',
  FIRE:      'fire',
  FLOOD:     'flood',
  VANDALISM: 'vandalism',
  OTHER:     'other',
} as const

export type IncidentType = (typeof IncidentType)[keyof typeof IncidentType]

// ── IncidentStatus ────────────────────────────────────────────────────────────

export const IncidentStatus = {
  PENDING:     'pending',
  ASSIGNED:    'assigned',
  IN_PROGRESS: 'in_progress',
  COMPLETED:   'completed',
  CANCELLED:   'cancelled',
} as const

export type IncidentStatus = (typeof IncidentStatus)[keyof typeof IncidentStatus]

export const ACTIVE_INCIDENT_STATUSES: ReadonlySet<IncidentStatus> = new Set([
  IncidentStatus.PENDING,
  IncidentStatus.ASSIGNED,
  IncidentStatus.IN_PROGRESS,
])

// ── AssignmentStatus ──────────────────────────────────────────────────────────

export const AssignmentStatus = {
  ASSIGNED:    'assigned',
  ACCEPTED:    'accepted',
  EN_ROUTE:    'en_route',
  ARRIVED:     'arrived',
  IN_PROGRESS: 'in_progress',
  COMPLETED:   'completed',
  CANCELLED:   'cancelled',
} as const

export type AssignmentStatus = (typeof AssignmentStatus)[keyof typeof AssignmentStatus]

export const ACTIVE_ASSIGNMENT_STATUSES: ReadonlySet<AssignmentStatus> = new Set([
  AssignmentStatus.ASSIGNED,
  AssignmentStatus.ACCEPTED,
  AssignmentStatus.EN_ROUTE,
  AssignmentStatus.ARRIVED,
  AssignmentStatus.IN_PROGRESS,
])

export const TERMINAL_ASSIGNMENT_STATUSES: ReadonlySet<AssignmentStatus> = new Set([
  AssignmentStatus.COMPLETED,
  AssignmentStatus.CANCELLED,
])

// ── AdjusterStatus ────────────────────────────────────────────────────────────

export const AdjusterStatus = {
  AVAILABLE: 'available',
  BUSY:      'busy',
  EN_ROUTE:  'en_route',
  ON_SITE:   'on_site',
  OFFLINE:   'offline',
} as const

export type AdjusterStatus = (typeof AdjusterStatus)[keyof typeof AdjusterStatus]

export const BUSY_ADJUSTER_STATUSES: ReadonlySet<AdjusterStatus> = new Set([
  AdjusterStatus.BUSY,
  AdjusterStatus.EN_ROUTE,
  AdjusterStatus.ON_SITE,
])

// ── SeverityLevel ─────────────────────────────────────────────────────────────

export type SeverityLevel = 1 | 2 | 3 | 4 | 5

// ── RouteProvider ─────────────────────────────────────────────────────────────

export const RouteProvider = {
  OSRM:     'osrm',
  VALHALLA: 'valhalla',
  GOOGLE:   'google',
} as const

export type RouteProvider = (typeof RouteProvider)[keyof typeof RouteProvider]
