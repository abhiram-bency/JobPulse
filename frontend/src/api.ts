export interface Job {
  id: number
  source_id: number
  external_id: string
  title: string
  company: string | null
  location: string | null
  description: string | null
  url: string
  published_at: string | null
  first_seen_at: string
  last_seen_at: string
  created_at: string
  updated_at: string
}

export interface Paginated<T> {
  items: T[]
  page: number
  page_size: number
  total: number
}

export type SyncStatus = 'running' | 'success' | 'failed' | 'suspicious'

export interface SyncRun {
  id: number
  source_id: number
  started_at: string
  completed_at: string | null
  status: SyncStatus
  jobs_found: number
  jobs_created: number
  jobs_updated: number
  jobs_skipped: number
  jobs_invalid: number
  error_message: string | null
  duration_ms: number | null
}

export type SourceHealth = 'healthy' | 'degraded' | 'failed'

export interface Source {
  id: number
  name: string
  type: string
  base_url: string
  enabled: boolean
  last_success_at: string | null
  last_failure_at: string | null
  created_at: string
  updated_at: string
  health: SourceHealth
  job_count: number
  last_sync: SyncRun | null
}

export interface SourceHealthInfo {
  id: number
  name: string
  type: string
  base_url: string
  enabled: boolean
  health: SourceHealth
  job_count: number
  last_success_at: string | null
  last_failure_at: string | null
  last_sync: SyncRun | null
}

export interface Health {
  status: string
  app: string
  version: string
  database: string
  timestamp: string
  sources: SourceHealthInfo[]
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

const API_BASE = '/api/v1'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (typeof body?.detail === 'string') detail = body.detail
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  return res.json() as Promise<T>
}

export interface JobFilters {
  search?: string
  location?: string
  company?: string
}

export function fetchHealth(): Promise<Health> {
  return request<Health>('/health')
}

export function fetchSources(): Promise<Source[]> {
  return request<Source[]>('/sources')
}

export function fetchJobs(params: {
  page: number
  page_size: number
  filters: JobFilters
}): Promise<Paginated<Job>> {
  const query = new URLSearchParams({
    page: String(params.page),
    page_size: String(params.page_size),
  })
  for (const [key, value] of Object.entries(params.filters)) {
    if (value && value.trim()) query.set(key, value.trim())
  }
  return request<Paginated<Job>>(`/jobs?${query.toString()}`)
}

export function fetchSyncRuns(page = 1, page_size = 10): Promise<Paginated<SyncRun>> {
  return request<Paginated<SyncRun>>(`/sync-runs?page=${page}&page_size=${page_size}`)
}

export function runSync(sourceId?: number): Promise<SyncRun> {
  return request<SyncRun>('/sync', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(sourceId ? { source_id: sourceId } : {}),
  })
}