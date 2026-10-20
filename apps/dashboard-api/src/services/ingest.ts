import {
  LIMITS,
  boardSchema,
  eventSchema,
  eventTypeSchema,
  type IngestResult
} from '@sak/contracts'
import type { ZodError, ZodIssue } from 'zod'
import { toUtc, type Db } from '../db.js'
import type { ProjectRow } from './projects.js'

const EVENT_SCHEMA = 'sak.event/1'
const BOARD_SCHEMA = 'sak.board/1'
const MAX_ERROR_CHARS = 300

type Rejected = IngestResult['rejected'][number]

/** Kürzt Fehlertexte; sie enthalten nur Pfade und Regeln, keine Rohdaten des Requests. */
function clip(text: string): string {
  return text.length > MAX_ERROR_CHARS ? `${text.slice(0, MAX_ERROR_CHARS - 1)}…` : text
}

/** Wählt bei Union-Fehlern den Zweig mit den wenigsten Problemen und fasst ihn lesbar zusammen. */
function describeIssues(error: ZodError): string {
  const flat: ZodIssue[] = []
  const walk = (issues: ZodIssue[]): void => {
    for (const issue of issues) {
      if (issue.code === 'invalid_union' && issue.unionErrors.length > 0) {
        const best = [...issue.unionErrors].sort((a, b) => a.issues.length - b.issues.length)[0]!
        walk(best.issues)
      } else {
        flat.push(issue)
      }
    }
  }
  walk(error.issues)
  return flat
    .slice(0, 3)
    .map((i) => {
      const path = i.path.length > 0 ? i.path.join('.') : '(root)'
      // Zod-Meldungen für Enums nennen den empfangenen Wert; hier nur die Regel ausgeben.
      const message = i.code === 'invalid_enum_value' ? 'unzulässiger Wert' : i.message
      return `${path}: ${message}`
    })
    .join('; ')
}

function eventIdOf(raw: unknown): string | undefined {
  if (typeof raw === 'object' && raw !== null && 'event_id' in raw) {
    const id = (raw as { event_id: unknown }).event_id
    if (typeof id === 'string' && id.length > 0) return id.slice(0, 100)
  }
  return undefined
}

function reject(raw: unknown, error: string): Rejected {
  const event_id = eventIdOf(raw)
  return event_id ? { event_id, error: clip(error) } : { error: clip(error) }
}

export interface IngestInput {
  events: unknown[]
  board?: unknown
}

export function ingest(db: Db, project: ProjectRow, input: IngestInput, nowMs: number = Date.now()): IngestResult {
  const receivedAt = toUtc(nowMs)
  const rejected: Rejected[] = []
  let accepted = 0
  let duplicates = 0
  let boardAccepted = false

  const insertEvent = db.prepare(
    'INSERT OR IGNORE INTO events (event_id, project, run_id, type, ts, body, received_at) VALUES (?, ?, ?, ?, ?, ?, ?)'
  )

  const run = db.transaction(() => {
    for (const raw of input.events) {
      if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
        rejected.push({ error: 'event muss ein Objekt sein' })
        continue
      }
      const candidate = raw as Record<string, unknown>
      if (candidate.project !== project.key) {
        rejected.push(reject(raw, 'project mismatch'))
        continue
      }
      if (candidate.schema !== EVENT_SCHEMA) {
        rejected.push(reject(raw, `unsupported schema version (erwartet ${EVENT_SCHEMA})`))
        continue
      }
      if (Buffer.byteLength(JSON.stringify(raw)) > LIMITS.EVENT_MAX_BYTES) {
        rejected.push(reject(raw, `event zu groß (max ${LIMITS.EVENT_MAX_BYTES} Bytes)`))
        continue
      }
      if (typeof candidate.type === 'string' && candidate.type !== 'diag.hook' && !eventTypeSchema.safeParse(candidate.type).success) {
        rejected.push(reject(raw, 'unknown event type'))
        continue
      }
      const parsed = eventSchema.safeParse(raw)
      if (!parsed.success) {
        rejected.push(reject(raw, `ungültiges event: ${describeIssues(parsed.error)}`))
        continue
      }
      const event = parsed.data
      const result = insertEvent.run(
        event.event_id,
        project.key,
        event.run_id ?? null,
        event.type,
        toUtc(event.ts),
        // Gespeichert wird nur das validierte Contract-Objekt (Constitution II).
        JSON.stringify(event),
        receivedAt
      )
      if (result.changes === 0) duplicates += 1
      else accepted += 1
    }

    if (input.board !== undefined) {
      const rawBoard = input.board
      const boardSchemaId =
        typeof rawBoard === 'object' && rawBoard !== null ? (rawBoard as Record<string, unknown>).schema : undefined
      if (boardSchemaId !== BOARD_SCHEMA) {
        rejected.push({ error: `board: unsupported schema version (erwartet ${BOARD_SCHEMA})` })
      } else if (Buffer.byteLength(JSON.stringify(rawBoard)) > LIMITS.BOARD_MAX_BYTES) {
        rejected.push({ error: `board: zu groß (max ${LIMITS.BOARD_MAX_BYTES} Bytes)` })
      } else {
        const parsed = boardSchema.safeParse(rawBoard)
        if (!parsed.success) {
          rejected.push({ error: clip(`board: ungültig: ${describeIssues(parsed.error)}`) })
        } else if (parsed.data.project.key !== project.key) {
          rejected.push({ error: 'board: project mismatch' })
        } else {
          const generatedAt = toUtc(parsed.data.generated_at)
          const existing = db.prepare('SELECT generated_at FROM boards WHERE project = ?').get(project.key) as
            | { generated_at: string }
            | undefined
          // Veraltete oder gleich alte Boards werden nicht übernommen (board_accepted=false, kein Fehler).
          if (!existing || generatedAt > existing.generated_at) {
            db.prepare(
              `INSERT INTO boards (project, generated_at, body, received_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(project) DO UPDATE SET generated_at = excluded.generated_at, body = excluded.body, received_at = excluded.received_at`
            ).run(project.key, generatedAt, JSON.stringify(parsed.data), receivedAt)
            boardAccepted = true
          }
        }
      }
    }

    db.prepare('UPDATE projects SET last_ingest_at = ? WHERE key = ?').run(receivedAt, project.key)
  })
  run()

  return { schema: 'sak.ingest_result/1', accepted, duplicates, rejected, board_accepted: boardAccepted }
}
