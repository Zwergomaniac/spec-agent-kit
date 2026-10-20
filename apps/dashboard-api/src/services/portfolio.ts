import type { Db } from '../db.js'
import { listProjects, type ProjectRow } from './projects.js'
import { getBoard, type BoardRun } from './runs.js'

const DAY_MS = 24 * 60 * 60 * 1000

export type PortfolioWarning = 'stale' | 'idle' | 'no_push_24h'

export interface PortfolioProject {
  key: string
  name: string
  has_board: boolean
  board_generated_at: string | null
  last_ingest_at: string | null
  last_activity: string | null
  active_run: {
    run_id: string
    spec: string
    state: BoardRun['state']
    round: number
    max_rounds: number
    current_station: { role: string; agent: string; state: string } | null
    idle: boolean
    stale: boolean
  } | null
  /** Eskalierter Lauf (bevorzugt der aktive) mit offenem Grund. */
  escalation: { run_id: string; spec: string; reason: string | null } | null
  attention_count: number
  in_progress: number
  warnings: PortfolioWarning[]
}

export interface Portfolio {
  generated_at: string
  projects: PortfolioProject[]
}

function maxTs(values: Array<string | null | undefined>): string | null {
  let best: string | null = null
  for (const v of values) {
    if (!v) continue
    if (best === null || Date.parse(v) > Date.parse(best)) best = v
  }
  return best
}

function summarize(db: Db, project: ProjectRow, nowMs: number): PortfolioProject {
  const stored = getBoard(db, project.key)
  const board = stored?.board
  const lastEvent = db.prepare('SELECT MAX(ts) AS ts FROM events WHERE project = ?').get(project.key) as { ts: string | null }
  const lastActivity = maxTs([project.last_ingest_at, board?.generated_at, lastEvent.ts])

  const warnings: PortfolioWarning[] = []
  const active = board?.runs.find((r) => r.active) ?? null
  if (active?.stale) warnings.push('stale')
  if (active?.idle) warnings.push('idle')
  const pushReference = project.last_ingest_at ?? project.created_at
  if (nowMs - Date.parse(pushReference) > DAY_MS) warnings.push('no_push_24h')

  const escalatedRun = board ? (board.runs.find((r) => r.active && r.state === 'escalated') ?? board.runs.find((r) => r.state === 'escalated')) : undefined
  const openEscalation = escalatedRun ? ([...escalatedRun.escalations].reverse().find((e) => e.open) ?? null) : null

  const lastStation = active ? ([...active.stations].reverse().find((s) => s.state === 'running') ?? active.stations.at(-1)) : undefined

  return {
    key: project.key,
    name: board?.project.name ?? project.name,
    has_board: board !== undefined,
    board_generated_at: board?.generated_at ?? null,
    last_ingest_at: project.last_ingest_at,
    last_activity: lastActivity,
    active_run: active
      ? {
          run_id: active.run_id,
          spec: active.spec,
          state: active.state,
          round: active.round,
          max_rounds: active.max_rounds,
          current_station: lastStation ? { role: lastStation.role, agent: lastStation.agent, state: lastStation.state } : null,
          idle: active.idle,
          stale: active.stale
        }
      : null,
    escalation: escalatedRun
      ? { run_id: escalatedRun.run_id, spec: escalatedRun.spec, reason: openEscalation?.reason ?? null }
      : null,
    attention_count: board?.attention.length ?? 0,
    in_progress: board?.metrics.in_progress ?? 0,
    warnings
  }
}

export function buildPortfolio(db: Db, nowMs: number = Date.now()): Portfolio {
  return {
    generated_at: new Date(nowMs).toISOString(),
    projects: listProjects(db).map((p) => summarize(db, p, nowMs))
  }
}
