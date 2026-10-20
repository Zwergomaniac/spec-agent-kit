# Implementation Plan: Dashboard v1

**Branch**: `007-dashboard-v1` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

## Technical Context

- **Sprache:** TypeScript 5.x, Node 22 LTS im Container.
- **API:** `hono`, `@hono/node-server`, `better-sqlite3`, `@sak/contracts` (Zod). Sessions sind eigene HMAC-signierte Cookies (`node:crypto`), Passwörter werden mit `scrypt` gehasht.
- **UI:** `react` 18, `vite`, `tailwindcss`, shadcn/ui (Komponenten eingecheckt unter `src/components/ui`), `lucide-react`, `recharts`. Das Routing ist ein eigener kleiner Hash-Router auf Basis von `@sak/contracts/deep-links`, ohne react-router.
- **Tests:**
  - vitest für API-Vertragstests mit `app.request()` und In-Memory-SQLite
  - vitest + Testing Library für UI-Einheiten
  - Playwright für E2E-Deep-Links und den Screenshot-Smoke-Test
- **Rahmen:** ressourcenschonend (SC-003), keine weiteren Laufzeit-Abhängigkeiten ohne Begründung.

## Constitution Check

| Prinzip | Erfüllt durch |
|---|---|
| I | Alle Ein- und Ausgaben laufen über `@sak/contracts`. Vokabular und Labels kommen von dort. |
| II | Es wird nur Validiertes gespeichert, und Request-Bodies werden nicht geloggt. |
| IV | Session-Pflicht, Bearer-Token-Hashes, Rate-Limits, Login-Sperre, non-root-Container. |
| VII | Vertragstests, E2E, Statusmatrix. |

## Project Structure

```text
apps/dashboard-api/
  package.json             # @sak/dashboard-api; scripts dev, build (tsc), start, test, hash-password, project (CLI)
  src/
    server.ts              # serve() Einstieg; Env prüfen; Migration; Retention-Timer; statische UI aus ../dashboard-web/dist (Pfad per Env SAK_WEB_DIST)
    app.ts                 # createApp(deps) – testbar ohne Netz
    env.ts db.ts migrations.ts
    auth/session.ts auth/password.ts auth/rate-limit.ts
    routes/health.ts auth.ts ingest.ts read.ts admin.ts meta.ts
    services/ingest.ts portfolio.ts runs.ts retention.ts projects.ts
    cli/hash-password.ts cli/project.ts   # project add|list|rotate|remove
  test/*.test.ts
apps/dashboard-web/
  package.json index.html vite.config.ts tailwind.config.ts postcss.config.js components.json
  src/
    main.tsx App.tsx router.ts api.ts labels.ts theme.ts
    views/Login.tsx Portfolio.tsx Project.tsx Run.tsx Admin.tsx
    views/project/BoardTab.tsx RunsTab.tsx AttentionTab.tsx ConflictsTab.tsx
    components/ (ProjectCard, StageColumn, SpecCard, AttentionList, RunPanel, StationTimeline, Ticker, Kpis, charts/*)
    components/ui/          # shadcn
  test/  e2e/
deploy/dashboard/
  Dockerfile compose.snippet.yml caddy.example README.md
```

Die bisherigen Mock-Dateien `apps/dashboard-api/src/server.js` und `apps/dashboard-web/AGENTS.md` werden ersetzt bzw. aktualisiert.

## Datenmodell (SQLite)

```sql
projects(key TEXT PK, name TEXT NOT NULL, token_hash TEXT NOT NULL, created_at TEXT, last_ingest_at TEXT)
events(event_id TEXT PK, project TEXT REFERENCES projects(key) ON DELETE CASCADE, run_id TEXT, type TEXT, ts TEXT, body TEXT, received_at TEXT)
  INDEX events(project, run_id), events(project, ts)
boards(project TEXT PK REFERENCES projects(key) ON DELETE CASCADE, generated_at TEXT, body TEXT, received_at TEXT)
login_failures(ip TEXT, at TEXT)
schema_migrations(version INTEGER)
```

## Portfolio-Berechnung

Je Projekt:
- **aktiver Lauf:** der erste aus `board.runs` mit `active`
- **Zahlen:** Anzahl `attention` und `metrics.in_progress`
- **`last_activity`:** das Maximum aus `last_ingest_at`, `board.generated_at` und dem letzten Event-`ts`
- **Warnungen:**
  - `stale`/`idle` aus dem aktiven Lauf
  - `no_push_24h`

## Complexity Tracking

Keine Verstöße.
