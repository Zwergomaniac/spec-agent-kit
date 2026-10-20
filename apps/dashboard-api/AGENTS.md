# AGENTS.md

Hono-API mit SQLite (WAL). Sie liefert auch die gebaute UI aus `apps/dashboard-web/dist` aus (SPA-Fallback in `src/static.ts`).

- Das Dashboard speichert nur Metadaten. Ingest validiert gegen `@sak/contracts` (Zod), lehnt unbekannte und zu große Felder ab und meldet Einzelfehler pro Event in `rejected[]` (HTTP 200). Anfragegrenze 2 MB.
- Jeder Schreibzugriff ist authentifiziert: Ingest per Projekt-Schlüssel (`Authorization: Bearer sak_…`, Projekt ergibt sich aus dem Schlüssel), Lesen und Admin per Session-Cookie. Keine Stacktraces nach außen.
- Konfiguration nur über Umgebungsvariablen (`src/env.ts`): `SAK_ADMIN_PASSWORD_HASH` und `SAK_SESSION_SECRET` sind Pflicht, sonst verweigert der Start. Neue Variablen gehören auch in `deploy/dashboard/README.md`.
- Routen: `/healthz`, `/api/auth`, `/api/ingest`, `/api/admin`, `/api/meta`, `/api/portfolio`, `/api/projects/:key[/runs/:runId|/events]`.
- Eigene Vokabularwerte gibt es nicht; Zustände und Begriffe kommen aus `packages/contracts`. Ausnahme: die Portfolio-Warnungen `stale`, `idle`, `no_push_24h` (siehe `docs/follow-ups.md`).
- Build: esbuild-Bundle (`scripts/build.mjs`) nach `dist/`, nur `better-sqlite3` bleibt extern. `pnpm --filter @sak/dashboard-api lint` ist nur `tsc` (Typprüfung).
- Tests: `pnpm --filter @sak/dashboard-api test` (vitest, API-Vertragstests). CLIs nach dem Build: `node dist/cli/hash-password.js`, `node dist/cli/project.js add|list|rotate|remove`.
- Dev: `pnpm --filter @sak/dashboard-api dev` (tsx watch). Lokal ohne TLS nur mit `NODE_ENV=development` (sonst ist das Cookie `Secure`).
