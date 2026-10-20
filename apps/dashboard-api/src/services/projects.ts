import { createHash, randomBytes, timingSafeEqual } from 'node:crypto'
import { nameSchema, projectKeySchema } from '@sak/contracts'
import type { Db } from '../db.js'

export interface ProjectRow {
  key: string
  name: string
  created_at: string
  last_ingest_at: string | null
}

interface ProjectRowWithHash extends ProjectRow {
  token_hash: string
}

export class ProjectError extends Error {
  constructor(
    public readonly code: 'invalid_key' | 'invalid_name' | 'exists' | 'not_found',
    message: string
  ) {
    super(message)
    this.name = 'ProjectError'
  }
}

export function hashToken(token: string): string {
  return createHash('sha256').update(token).digest('hex')
}

/** 256 Bit zufällig, base64url; Präfix macht Schlüssel in Secret-Scannern erkennbar. */
export function generateToken(): string {
  return `sak_${randomBytes(32).toString('base64url')}`
}

const PUBLIC_COLUMNS = 'key, name, created_at, last_ingest_at'

export function listProjects(db: Db): ProjectRow[] {
  return db.prepare(`SELECT ${PUBLIC_COLUMNS} FROM projects ORDER BY key`).all() as ProjectRow[]
}

export function getProject(db: Db, key: string): ProjectRow | undefined {
  return db.prepare(`SELECT ${PUBLIC_COLUMNS} FROM projects WHERE key = ?`).get(key) as ProjectRow | undefined
}

/** Legt ein Projekt an. Der Klartext-Schlüssel wird nur hier zurückgegeben und nie gespeichert. */
export function createProject(db: Db, key: string, name: string, nowMs: number = Date.now()): { project: ProjectRow; token: string } {
  if (!projectKeySchema.safeParse(key).success) {
    throw new ProjectError('invalid_key', 'Ungültiger Projektschlüssel (2 bis 40 Zeichen: a-z, 0-9, Bindestrich).')
  }
  if (!nameSchema.safeParse(name).success) {
    throw new ProjectError('invalid_name', 'Ungültiger Name (1 bis 100 Zeichen).')
  }
  if (getProject(db, key)) throw new ProjectError('exists', `Projekt ${key} existiert bereits.`)
  const token = generateToken()
  const createdAt = new Date(nowMs).toISOString()
  db.prepare('INSERT INTO projects (key, name, token_hash, created_at) VALUES (?, ?, ?, ?)').run(key, name, hashToken(token), createdAt)
  return { project: { key, name, created_at: createdAt, last_ingest_at: null }, token }
}

export function rotateProjectToken(db: Db, key: string): { project: ProjectRow; token: string } {
  const project = getProject(db, key)
  if (!project) throw new ProjectError('not_found', `Projekt ${key} existiert nicht.`)
  const token = generateToken()
  db.prepare('UPDATE projects SET token_hash = ? WHERE key = ?').run(hashToken(token), key)
  return { project, token }
}

/** Entfernt das Projekt samt Events und Board (ON DELETE CASCADE). */
export function removeProject(db: Db, key: string): void {
  const result = db.prepare('DELETE FROM projects WHERE key = ?').run(key)
  if (result.changes === 0) throw new ProjectError('not_found', `Projekt ${key} existiert nicht.`)
}

/**
 * Ordnet einen Bearer-Schlüssel einem Projekt zu. Vergleicht mit allen Projekten und ohne
 * vorzeitigen Abbruch, jeweils in konstanter Zeit (FR-004).
 */
export function authenticateProjectToken(db: Db, token: string): ProjectRow | undefined {
  const given = Buffer.from(hashToken(token), 'hex')
  const rows = db.prepare(`SELECT ${PUBLIC_COLUMNS}, token_hash FROM projects`).all() as ProjectRowWithHash[]
  let found: ProjectRow | undefined
  for (const row of rows) {
    const stored = Buffer.from(row.token_hash, 'hex')
    if (stored.length === given.length && timingSafeEqual(stored, given)) {
      const { token_hash: _omit, ...publicRow } = row
      found = publicRow
    }
  }
  return found
}
