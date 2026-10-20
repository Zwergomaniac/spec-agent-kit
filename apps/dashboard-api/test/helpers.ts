import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import type { Board, IngestRequest, SakEvent } from '@sak/contracts'
import { createApp } from '../src/app.js'
import { hashPassword } from '../src/auth/password.js'
import { openDb, type Db } from '../src/db.js'
import { createProject } from '../src/services/projects.js'

export const ADMIN_PASSWORD = 'test-passwort-nur-fuer-tests'
export const SESSION_SECRET = 'test-secret-test-secret-test-secret-0123456789'
/** Fester Zeitpunkt kurz nach dem Pilot-Board (2026-10-20T10:20+02:00). */
export const NOW = Date.parse('2026-10-20T09:00:00Z')

let cachedHash: Promise<string> | undefined
export function adminHash(): Promise<string> {
  cachedHash ??= hashPassword(ADMIN_PASSWORD)
  return cachedHash
}

export function loadExample<T>(name: string): T {
  const url = new URL(`../../../packages/contracts/examples/valid/${name}`, import.meta.url)
  return JSON.parse(readFileSync(fileURLToPath(url), 'utf8')) as T
}

export const pilotBoard = (): Board => loadExample<Board>('board-pilot-immo-agent.json')

export interface TestCtx {
  db: Db
  app: ReturnType<typeof createApp>
  clock: { now: number }
  request: (path: string, init?: RequestInit & { cookie?: string }) => Promise<Response>
  login: () => Promise<string>
  addProject: (key: string, name?: string) => string
  ingestAs: (token: string, body: unknown, init?: RequestInit) => Promise<Response>
}

export async function createTestCtx(opts: { webDist?: string | null; trustProxy?: boolean } = {}): Promise<TestCtx> {
  const db = openDb(':memory:')
  const clock = { now: NOW }
  const app = createApp({
    db,
    now: () => clock.now,
    env: {
      sessionSecret: SESSION_SECRET,
      adminPasswordHash: await adminHash(),
      secureCookie: true,
      trustProxy: opts.trustProxy ?? true,
      webDist: opts.webDist ?? null
    }
  })

  const request: TestCtx['request'] = (path, init = {}) => {
    const { cookie, headers, ...rest } = init
    const h = new Headers(headers)
    if (cookie) h.set('cookie', cookie)
    return Promise.resolve(app.request(path, { ...rest, headers: h }))
  }

  const login = async (): Promise<string> => {
    const res = await request('/api/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ password: ADMIN_PASSWORD })
    })
    if (res.status !== 200) throw new Error(`Login fehlgeschlagen: ${res.status}`)
    const setCookie = res.headers.get('set-cookie') ?? ''
    return setCookie.split(';')[0]!
  }

  const addProject = (key: string, name = key): string => createProject(db, key, name, clock.now).token

  const ingestAs: TestCtx['ingestAs'] = (token, body, init = {}) =>
    request('/api/ingest', {
      method: 'POST',
      ...init,
      headers: { 'content-type': 'application/json', authorization: `Bearer ${token}`, ...(init.headers as Record<string, string>) },
      body: typeof body === 'string' ? body : JSON.stringify(body)
    })

  return { db, app, clock, request, login, addProject, ingestAs }
}

export function ingestRequest(project: string, events: SakEvent[], board?: Board): IngestRequest {
  return {
    schema: 'sak.ingest/1',
    project,
    sent_at: '2026-10-20T10:25:00+02:00',
    events,
    ...(board ? { board } : {})
  }
}

/** Leitet aus Lauf 088 des Pilot-Boards eine plausible Event-Folge ab (Start, Runden, Stationen, Urteile, Eskalation). */
export function pilotEvents(): SakEvent[] {
  const board = pilotBoard()
  const run = board.runs.find((r) => r.run_id === '088-20261019-101500')!
  const base = { schema: 'sak.event/1' as const, project: 'immo-agent', run_id: run.run_id, spec: run.spec }
  const events: SakEvent[] = []
  const push = (type: string, ts: string, data: unknown): void => {
    counter += 1
    events.push({ ...base, event_id: `01K8M3Q7R5${String(counter).padStart(16, '0')}`, type, ts, data } as SakEvent)
  }
  push('run.started', run.started_at, { kind: run.kind, base_branch: 'main', base_commit: 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678', max_rounds: run.max_rounds })
  let lastRound = 0
  for (const s of run.stations) {
    if (s.round !== lastRound) {
      push('round.started', s.started_at, { round: s.round })
      lastRound = s.round
    }
    push('station.started', s.started_at, { round: s.round, role: s.role, agent: s.agent })
    const end = new Date(Date.parse(s.started_at) + (s.duration_s ?? 0) * 1000).toISOString()
    if (s.state === 'finished') push('station.finished', end, { round: s.round, role: s.role, agent: s.agent, duration_s: s.duration_s ?? 0 })
    if (s.verdict) push('verdict.recorded', end, { round: s.round, role: s.role, verdict: s.verdict, must_count: s.must_count ?? 0, may_count: s.may_count ?? 0 })
  }
  for (const e of run.escalations) push('run.escalated', e.ts, { round: e.round, gate: e.gate, reason: e.reason })
  return events
}

let counter = 100
/** Erzeugt ein gültiges `round.started`-Event mit eindeutiger ULID. */
export function makeEvent(project: string, overrides: Partial<SakEvent> = {}): SakEvent {
  counter += 1
  const id = `01K8M3Q7R5${String(counter).padStart(16, '0')}`
  return {
    schema: 'sak.event/1',
    event_id: id,
    type: 'round.started',
    ts: '2026-10-20T10:00:00+02:00',
    project,
    run_id: '088-20261019-101500',
    spec: '088-kartenansicht',
    data: { round: 1 },
    ...overrides
  } as SakEvent
}
