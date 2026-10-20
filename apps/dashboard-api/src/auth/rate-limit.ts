import type { Db } from '../db.js'

/** Fester Zeitfenster-Zähler im Speicher (Ingest: 60 Requests pro Minute und Projekt, FR-004). */
export class WindowRateLimiter {
  private readonly buckets = new Map<string, { start: number; count: number }>()

  constructor(
    private readonly limit: number,
    private readonly windowMs: number
  ) {}

  /** Zählt einen Zugriff. Liefert false, wenn das Limit überschritten ist. */
  hit(key: string, nowMs: number = Date.now()): boolean {
    const bucket = this.buckets.get(key)
    if (!bucket || nowMs - bucket.start >= this.windowMs) {
      this.buckets.set(key, { start: nowMs, count: 1 })
      this.sweep(nowMs)
      return true
    }
    bucket.count += 1
    return bucket.count <= this.limit
  }

  private sweep(nowMs: number): void {
    if (this.buckets.size < 1000) return
    for (const [k, b] of this.buckets) if (nowMs - b.start >= this.windowMs) this.buckets.delete(k)
  }
}

export const LOGIN_MAX_FAILURES = 5
export const LOGIN_LOCK_MS = 15 * 60 * 1000

/** Login-Sperre pro IP: 15 min nach 5 Fehlversuchen (Spec 007, Edge Cases). Zustand in SQLite. */
export class LoginGuard {
  constructor(private readonly db: Db) {}

  /** Sekunden bis zur Entsperrung, oder 0 wenn die IP nicht gesperrt ist. */
  lockedForSeconds(ip: string, nowMs: number = Date.now()): number {
    const since = new Date(nowMs - LOGIN_LOCK_MS).toISOString()
    const rows = this.db
      .prepare('SELECT at FROM login_failures WHERE ip = ? AND at > ? ORDER BY at DESC LIMIT ?')
      .all(ip, since, LOGIN_MAX_FAILURES) as Array<{ at: string }>
    if (rows.length < LOGIN_MAX_FAILURES) return 0
    const fifth = Date.parse(rows[LOGIN_MAX_FAILURES - 1]!.at)
    return Math.max(1, Math.ceil((fifth + LOGIN_LOCK_MS - nowMs) / 1000))
  }

  recordFailure(ip: string, nowMs: number = Date.now()): void {
    this.db.prepare('INSERT INTO login_failures (ip, at) VALUES (?, ?)').run(ip, new Date(nowMs).toISOString())
  }

  clear(ip: string): void {
    this.db.prepare('DELETE FROM login_failures WHERE ip = ?').run(ip)
  }
}
