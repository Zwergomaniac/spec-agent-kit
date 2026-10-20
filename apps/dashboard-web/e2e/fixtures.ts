import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import type { Board, SakEvent } from '@sak/contracts'

export const BASE_URL = 'http://127.0.0.1:3100'
export const ADMIN_PASSWORD = 'e2e-test-passwort-123'
export const SESSION_SECRET = 'e2e-session-secret-e2e-session-secret-0123'

export const PILOT_KEY = 'immo-agent'
export const PILOT_RUN = '088-20261019-101500'
export const SECOND_KEY = 'spec-agent-kit'

export function pilotBoard(): Board {
  const url = new URL('../../../packages/contracts/examples/valid/board-pilot-immo-agent.json', import.meta.url)
  return JSON.parse(readFileSync(fileURLToPath(url), 'utf8')) as Board
}

/** Leitet aus den Läufen des Pilot-Boards eine Event-Folge ab (Start, Runden, Stationen, Urteile, Eskalation). */
export function pilotEvents(board: Board): SakEvent[] {
  const events: SakEvent[] = []
  let n = 0
  const push = (runId: string, spec: string, type: string, ts: string, data: unknown): void => {
    n += 1
    events.push({
      schema: 'sak.event/1',
      event_id: `01K8M3Q7R5${String(n).padStart(16, '0')}`,
      type,
      ts,
      project: board.project.key,
      run_id: runId,
      spec,
      data
    } as SakEvent)
  }
  for (const run of board.runs) {
    push(run.run_id, run.spec, 'run.started', run.started_at, {
      kind: run.kind,
      base_branch: 'main',
      base_commit: 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678',
      max_rounds: run.max_rounds
    })
    let lastRound = 0
    for (const s of run.stations) {
      if (s.round !== lastRound) {
        push(run.run_id, run.spec, 'round.started', s.started_at, { round: s.round })
        lastRound = s.round
      }
      push(run.run_id, run.spec, 'station.started', s.started_at, { round: s.round, role: s.role, agent: s.agent })
      const end = new Date(Date.parse(s.started_at) + (s.duration_s ?? 0) * 1000).toISOString()
      if (s.state === 'finished') push(run.run_id, run.spec, 'station.finished', end, { round: s.round, role: s.role, agent: s.agent, duration_s: s.duration_s ?? 0 })
      if (s.verdict) push(run.run_id, run.spec, 'verdict.recorded', end, { round: s.round, role: s.role, verdict: s.verdict, must_count: s.must_count ?? 0, may_count: s.may_count ?? 0 })
    }
    for (const e of run.escalations) push(run.run_id, run.spec, 'run.escalated', e.ts, { round: e.round, gate: e.gate, reason: e.reason })
    if (run.state === 'paused') push(run.run_id, run.spec, 'run.paused', run.updated_at, { reason: 'Betreiber hat pausiert' })
    if (run.state === 'merged') push(run.run_id, run.spec, 'run.merged', run.updated_at, {})
  }
  return events
}

export function secondBoard(base: Board): Board {
  return {
    ...base,
    project: { key: SECOND_KEY, name: 'Spec Agent Kit', base_branch: 'main' },
    metrics: { in_progress: 1, done: 6, blocked: 0, waiting: 0, mean_lead_time_days: 2.1 },
    specs: base.specs.slice(0, 3),
    attention: [],
    runs: [],
    markers: [],
    ticker: [],
    notes: []
  }
}

/** Weitere Projekte, damit das Portfolio-Raster auf breiten Fenstern mehrere Karten je Zeile zeigt. */
export const EXTRA_PROJECTS = [
  { key: 'ai-forge', name: 'AI Forge', specs: 8 },
  { key: 'kundenportal', name: 'Kundenportal', specs: 5 },
  { key: 'specboard', name: 'Specboard', specs: 10 },
  { key: 'docs-hub', name: 'Docs Hub', specs: 6 },
  { key: 'infra-tools', name: 'Infra Tools', specs: 9 }
] as const

export function extraBoard(base: Board, key: string, name: string, specs: number): Board {
  return {
    ...base,
    project: { key, name, base_branch: 'main' },
    metrics: { ...base.metrics, in_progress: 2, done: specs - 3, blocked: 0 },
    specs: base.specs.filter((s) => !s.descoped).slice(0, specs),
    attention: base.attention.slice(0, 1),
    runs: [],
    ticker: [],
    notes: []
  }
}
