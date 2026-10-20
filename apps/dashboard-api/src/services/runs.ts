import { LIMITS, type Board, type SakEvent } from '@sak/contracts'
import type { Db } from '../db.js'

export type BoardRun = Board['runs'][number]

export function getBoard(db: Db, project: string): { board: Board; received_at: string } | undefined {
  const row = db.prepare('SELECT body, received_at FROM boards WHERE project = ?').get(project) as
    | { body: string; received_at: string }
    | undefined
  if (!row) return undefined
  return { board: JSON.parse(row.body) as Board, received_at: row.received_at }
}

export function countEvents(db: Db, project: string): number {
  const row = db.prepare('SELECT COUNT(*) AS n FROM events WHERE project = ?').get(project) as { n: number }
  return row.n
}

export interface EventQuery {
  run?: string
  since?: string
  limit: number
}

/**
 * Ohne `since` die neuesten `limit` Events (aufsteigend sortiert); mit `since` die ersten `limit`
 * Events nach diesem Zeitpunkt, aufsteigend (für inkrementelles Nachladen).
 */
export function listEvents(db: Db, project: string, q: EventQuery): SakEvent[] {
  const limit = Math.min(Math.max(1, q.limit), LIMITS.INGEST_MAX_EVENTS)
  const where = ['project = ?']
  const params: unknown[] = [project]
  if (q.run) {
    where.push('run_id = ?')
    params.push(q.run)
  }
  if (q.since) {
    where.push('ts > ?')
    params.push(q.since)
    const rows = db
      .prepare(`SELECT body FROM events WHERE ${where.join(' AND ')} ORDER BY ts ASC, event_id ASC LIMIT ?`)
      .all(...params, limit) as Array<{ body: string }>
    return rows.map((r) => JSON.parse(r.body) as SakEvent)
  }
  const rows = db
    .prepare(`SELECT body FROM events WHERE ${where.join(' AND ')} ORDER BY ts DESC, event_id DESC LIMIT ?`)
    .all(...params, limit) as Array<{ body: string }>
  return rows.reverse().map((r) => JSON.parse(r.body) as SakEvent)
}

export interface RunDetail {
  project: string
  run: BoardRun | null
  events: SakEvent[]
}

/** Lauf aus dem Board plus dessen Events. Undefined, wenn weder Lauf noch Events existieren. */
export function getRunDetail(db: Db, project: string, runId: string): RunDetail | undefined {
  const board = getBoard(db, project)?.board
  const run = board?.runs.find((r) => r.run_id === runId) ?? null
  const events = listEvents(db, project, { run: runId, limit: LIMITS.INGEST_MAX_EVENTS })
  if (!run && events.length === 0) return undefined
  return { project, run, events }
}
