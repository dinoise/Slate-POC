import type {
  Incident,
  Adjuster,
  AdjusterCreate,
  Assignment,
  AdjusterPosition,
  DemandPrediction,
  DemandSlot,
  User,
  PaginatedResponse,
  ProviderSettings,
  AssignmentStatus,
} from '@slate/types'

// ── Auth token ────────────────────────────────────────────────────────────────

let _authToken: string | null = null

export function setAuthToken(token: string | null): void {
  _authToken = token
}

export function getAuthToken(): string | null {
  return _authToken
}

// ── Base fetch ────────────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const baseUrl = (import.meta as ImportMeta & { env: { VITE_API_BASE_URL: string } }).env.VITE_API_BASE_URL ?? ''
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(init?.headers as Record<string, string>),
  }
  if (_authToken) {
    headers['Authorization'] = `Bearer ${_authToken}`
  }
  const res = await fetch(`${baseUrl}${path}`, { ...init, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail ?? 'API error')
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

// ── Incidents ─────────────────────────────────────────────────────────────────

export const incidentsApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return apiFetch<PaginatedResponse<Incident>>(`/api/v1/incidents${qs}`)
  },
  get: (id: number) => apiFetch<Incident>(`/api/v1/incidents/${id}`),
  create: (data: Partial<Incident>) =>
    apiFetch<Incident>('/api/v1/incidents', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<Incident>) =>
    apiFetch<Incident>(`/api/v1/incidents/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) => apiFetch<void>(`/api/v1/incidents/${id}`, { method: 'DELETE' }),
  nearby: (lat: number, lon: number, radiusKm = 10) =>
    apiFetch<Incident[]>(`/api/v1/incidents/nearby/?lat=${lat}&lon=${lon}&radius_km=${radiusKm}`),
}

// ── Adjusters ─────────────────────────────────────────────────────────────────

export const adjustersApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return apiFetch<PaginatedResponse<Adjuster>>(`/api/v1/adjusters${qs}`)
  },
  get: (id: number) => apiFetch<Adjuster>(`/api/v1/adjusters/${id}`),
  create: (data: AdjusterCreate) =>
    apiFetch<Adjuster>('/api/v1/adjusters', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<AdjusterCreate>) =>
    apiFetch<Adjuster>(`/api/v1/adjusters/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  delete: (id: number) => apiFetch<void>(`/api/v1/adjusters/${id}`, { method: 'DELETE' }),
  available: () => apiFetch<Adjuster[]>('/api/v1/adjusters/available'),
  resetStatus: () => apiFetch<void>('/api/v1/adjusters/reset-status', { method: 'POST' }),
}

// ── Assignments ───────────────────────────────────────────────────────────────

export const assignmentsApi = {
  list: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : ''
    return apiFetch<PaginatedResponse<Assignment>>(`/api/v1/assignments${qs}`)
  },
  get: (id: number) => apiFetch<Assignment>(`/api/v1/assignments/${id}`),
  updateStatus: (id: number, status: AssignmentStatus) =>
    apiFetch<Assignment>(`/api/v1/assignments/${id}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
  byIncident: (incidentId: number) =>
    apiFetch<Assignment[]>(`/api/v1/assignments/by-incident/${incidentId}`),
  byAdjuster: (adjusterId: number) =>
    apiFetch<Assignment[]>(`/api/v1/assignments/by-adjuster/${adjusterId}`),
}

// ── Adjuster Positions ────────────────────────────────────────────────────────

export const adjusterPositionsApi = {
  report: (data: { adjuster_id: number; latitude: number; longitude: number }) =>
    apiFetch<AdjusterPosition>('/api/v1/adjuster_positions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),
  latest: (adjusterId: number) =>
    apiFetch<AdjusterPosition>(`/api/v1/adjuster_positions/${adjusterId}/latest`),
}

// ── Demand Predictions ────────────────────────────────────────────────────────

export const demandApi = {
  slots: () =>
    apiFetch<DemandSlot[]>('/api/v1/demand-predictions/available-slots'),
  bySlot: (params: { hora_num: number; dia_semana_num: number; bbox: string }) => {
    const qs = new URLSearchParams({
      hora_num: String(params.hora_num),
      dia_semana_num: String(params.dia_semana_num),
      bbox: params.bbox,
    }).toString()
    return apiFetch<DemandPrediction[]>(`/api/v1/demand-predictions?${qs}`)
  },
}

// ── Users ─────────────────────────────────────────────────────────────────────

export const usersApi = {
  list: () => apiFetch<User[]>('/api/v1/users'),
  get: (id: number) => apiFetch<User>(`/api/v1/users/${id}`),
  create: (data: Partial<User>) =>
    apiFetch<User>('/api/v1/users', { method: 'POST', body: JSON.stringify(data) }),
  update: (id: number, data: Partial<User>) =>
    apiFetch<User>(`/api/v1/users/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  delete: (id: number) => apiFetch<void>(`/api/v1/users/${id}`, { method: 'DELETE' }),
}

// ── Settings ──────────────────────────────────────────────────────────────────

export const settingsApi = {
  get: () => apiFetch<ProviderSettings>('/api/v1/settings/provider'),
  update: (provider: string) =>
    apiFetch<ProviderSettings>('/api/v1/settings/provider', {
      method: 'PUT',
      body: JSON.stringify({ provider }),
    }),
}
