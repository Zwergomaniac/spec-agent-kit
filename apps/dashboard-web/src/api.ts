import type { AdminProject, MetaResponse, PortfolioResponse, ProjectResponse, RunResponse } from './types'

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly code: string,
    public readonly body: Record<string, unknown> = {}
  ) {
    super(`${status} ${code}`)
    this.name = 'ApiError'
  }
}

let onUnauthorized: (() => void) | null = null

/** Wird bei jeder 401-Antwort (außer beim Login selbst) aufgerufen: die Session ist abgelaufen. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

async function request<T>(path: string, init: RequestInit = {}, opts: { auth?: boolean } = {}): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body !== undefined) headers.set('content-type', 'application/json')
  let res: Response
  try {
    res = await fetch(path, { ...init, headers, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'network')
  }
  if (!res.ok) {
    let body: Record<string, unknown> = {}
    try {
      body = (await res.json()) as Record<string, unknown>
    } catch {
      // keine JSON-Antwort
    }
    if (res.status === 401 && opts.auth !== false) onUnauthorized?.()
    throw new ApiError(res.status, typeof body.error === 'string' ? body.error : 'error', body)
  }
  return (await res.json()) as T
}

const enc = encodeURIComponent

export const api = {
  me: () => request<{ authenticated: true }>('/api/auth/me', {}, { auth: false }),
  login: (password: string) =>
    request<{ ok: true }>('/api/auth/login', { method: 'POST', body: JSON.stringify({ password }) }, { auth: false }),
  logout: () => request<{ ok: true }>('/api/auth/logout', { method: 'POST' }, { auth: false }),
  meta: () => request<MetaResponse>('/api/meta'),
  portfolio: () => request<PortfolioResponse>('/api/portfolio'),
  project: (key: string) => request<ProjectResponse>(`/api/projects/${enc(key)}`),
  run: (key: string, runId: string) => request<RunResponse>(`/api/projects/${enc(key)}/runs/${enc(runId)}`),
  adminProjects: () => request<{ projects: AdminProject[] }>('/api/admin/projects'),
  adminCreate: (key: string, name: string) =>
    request<{ project: AdminProject; token: string }>('/api/admin/projects', { method: 'POST', body: JSON.stringify({ key, name }) }),
  adminRotate: (key: string) => request<{ project: AdminProject; token: string }>(`/api/admin/projects/${enc(key)}/rotate`, { method: 'POST' }),
  adminRemove: (key: string) => request<{ ok: true }>(`/api/admin/projects/${enc(key)}`, { method: 'DELETE' })
}
