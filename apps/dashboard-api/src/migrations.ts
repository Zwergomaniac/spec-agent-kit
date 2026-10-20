import type Database from 'better-sqlite3'

// Schema gemäß plan.md. Zeitstempel werden als UTC-ISO-String (Millisekunden, "Z") gespeichert,
// damit lexikografische Vergleiche korrekt sind. Das Originalevent bleibt unverändert in `body`.
const MIGRATIONS: Array<{ version: number; sql: string }> = [
  {
    version: 1,
    sql: `
      CREATE TABLE projects (
        key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        token_hash TEXT NOT NULL,
        created_at TEXT NOT NULL,
        last_ingest_at TEXT
      );
      CREATE TABLE events (
        event_id TEXT PRIMARY KEY,
        project TEXT NOT NULL REFERENCES projects(key) ON DELETE CASCADE,
        run_id TEXT,
        type TEXT NOT NULL,
        ts TEXT NOT NULL,
        body TEXT NOT NULL,
        received_at TEXT NOT NULL
      );
      CREATE INDEX events_project_run ON events(project, run_id);
      CREATE INDEX events_project_ts ON events(project, ts);
      CREATE TABLE boards (
        project TEXT PRIMARY KEY REFERENCES projects(key) ON DELETE CASCADE,
        generated_at TEXT NOT NULL,
        body TEXT NOT NULL,
        received_at TEXT NOT NULL
      );
      CREATE TABLE login_failures (
        ip TEXT NOT NULL,
        at TEXT NOT NULL
      );
      CREATE INDEX login_failures_ip ON login_failures(ip, at);
    `
  }
]

export function runMigrations(db: Database.Database): number {
  db.exec('CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER NOT NULL)')
  const row = db.prepare('SELECT MAX(version) AS v FROM schema_migrations').get() as { v: number | null }
  const current = row.v ?? 0
  const apply = db.transaction((m: { version: number; sql: string }) => {
    db.exec(m.sql)
    db.prepare('INSERT INTO schema_migrations (version) VALUES (?)').run(m.version)
  })
  let latest = current
  for (const m of MIGRATIONS) {
    if (m.version > current) {
      apply(m)
      latest = m.version
    }
  }
  return latest
}
