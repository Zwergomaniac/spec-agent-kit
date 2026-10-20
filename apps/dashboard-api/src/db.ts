import Database from 'better-sqlite3'
import { mkdirSync } from 'node:fs'
import { dirname } from 'node:path'
import { runMigrations } from './migrations.js'

export type Db = Database.Database

/** Öffnet (und legt bei Bedarf an) die SQLite-Datei, aktiviert WAL und führt die Migrationen aus. */
export function openDb(path: string): Db {
  if (path !== ':memory:') mkdirSync(dirname(path), { recursive: true })
  const db = new Database(path)
  if (path !== ':memory:') db.pragma('journal_mode = WAL')
  db.pragma('foreign_keys = ON')
  db.pragma('busy_timeout = 5000')
  db.pragma('synchronous = NORMAL')
  runMigrations(db)
  return db
}

/** UTC-ISO-String mit Millisekunden. */
export function toUtc(ts: string | number | Date): string {
  return new Date(ts).toISOString()
}
