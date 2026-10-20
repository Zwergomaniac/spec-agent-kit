import type { Db } from '../db.js'

const DAY_MS = 24 * 60 * 60 * 1000

/** Löscht Events älter als `retentionDays` (nach Event-ts) und alte Login-Fehlversuche. Boards bleiben. */
export function runRetention(db: Db, retentionDays: number, nowMs: number = Date.now()): { eventsDeleted: number } {
  const cutoff = new Date(nowMs - retentionDays * DAY_MS).toISOString()
  const events = db.prepare('DELETE FROM events WHERE ts < ?').run(cutoff)
  db.prepare('DELETE FROM login_failures WHERE at < ?').run(new Date(nowMs - DAY_MS).toISOString())
  return { eventsDeleted: events.changes }
}

/** Führt die Bereinigung sofort und danach täglich aus. Der Timer hält den Prozess nicht am Leben. */
export function startRetention(db: Db, retentionDays: number): () => void {
  const tick = (): void => {
    try {
      runRetention(db, retentionDays)
    } catch (err) {
      console.error('retention failed:', err instanceof Error ? err.name : 'unknown')
    }
  }
  tick()
  const timer = setInterval(tick, DAY_MS)
  timer.unref()
  return () => clearInterval(timer)
}
