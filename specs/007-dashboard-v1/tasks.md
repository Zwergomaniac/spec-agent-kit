# Tasks: Dashboard v1

**Input**: [spec.md](spec.md), [plan.md](plan.md), Spec 002 (Contracts), [../../docs/architecture.md](../../docs/architecture.md)

## Phase 1: Setup

- [X] T001 `apps/dashboard-api` und `apps/dashboard-web` als Workspace-Pakete. Den Mock `server.js` entfernen. Abhängigkeit auf `@sak/contracts` (workspace).
  - Anmerkung: Die API wird mit esbuild gebündelt (`scripts/build.mjs`) statt mit `tsc`, weil `@sak/contracts` TypeScript-Quellen exportiert. `tsc` läuft als `lint` (Typprüfung). Paketnamen: `@sak/dashboard-api`, `@sak/dashboard-web`.
- [X] T002 [P] Vite, Tailwind und shadcn-Grundgerüst; Dark Mode; Hash-Router auf Basis der Deep-Link-Helfer.
  - Anmerkung: Tailwind v4 (`@tailwindcss/vite`), daher entfallen `tailwind.config.ts` und `postcss.config.js`; die Tokens stehen in `src/index.css`. Die shadcn-Bausteine sind im shadcn-Stil von Hand unter `src/components/ui` eingecheckt (new-york, zinc).

## Phase 2: Grundlagen API

- [ ] T003 `env.ts` (Pflicht-Secrets), `db.ts` und `migrations.ts` (WAL, Schema aus plan.md).
- [ ] T004 `auth/password.ts` (scrypt), `auth/session.ts` (HMAC-Cookie), `auth/rate-limit.ts`, Login-Sperre. `cli/hash-password.ts`.
- [ ] T005 `app.ts` mit Fehlerbehandlung (JSON-Fehler, kein Stacktrace nach außen), `/healthz`, Auth-Routen und Auth-Middleware.

## Phase 3: US4 – Ingest

- [ ] T006 `services/projects.ts` und `cli/project.ts` (add, list, rotate, remove; Schlüssel einmalig ausgeben).
- [ ] T007 `routes/ingest.ts` und `services/ingest.ts` gemäß Spec FR-004 und FR-006, mit Größenlimit 2 MB.
- [ ] T008 `services/retention.ts` (täglich und beim Start).
- [ ] T009 Vertragstests für Ingest (SC-002).

## Phase 4: US1–US3 – Lese-API

- [ ] T010 `routes/meta.ts`, `routes/read.ts` und `services/portfolio.ts`, `services/runs.ts`.
- [ ] T011 Tests für die Lese-API mit dem Pilot-Board-Beispiel aus `packages/contracts/examples/valid/`.

## Phase 5: UI

- [ ] T012 Login mit Rücksprung zur Ziel-URL.
- [ ] T013 Portfolio: Projektkarten, Warnungen, Hervorhebung bei Eskalation.
- [ ] T014 Projekt: Tabs board, runs, attention, conflicts mit `?tab=`-Sync; Kennzahlen-Kacheln, Stationsspalten, „Mensch prüft“-Spalte, Agenten-Panel, Ticker, 2 Diagramme.
- [ ] T015 Lauf-Ansicht: Runden, Stationen, Urteile, Eskalationen, Event-Log.
- [ ] T016 Admin: Projekte verwalten.
- [ ] T017 Polling alle 10 s, sichtbar-abhängig; „zuletzt aktualisiert“; Fehler- und Leerzustände; Labels über Contracts, unbekannte Werte als „unbekannt (wert)“.

## Phase 6: Deploy

- [ ] T018 `deploy/dashboard/Dockerfile` (Multi-Stage, non-root, Healthcheck), `compose.snippet.yml` (externes Netz `${SAK_EDGE_NETWORK:-edge}`), `caddy.example`, `README.md` (Betrieb, Secrets, Projekt anlegen).
- [ ] T019 `server.ts` liefert die statische UI aus, mit SPA-Fallback auf index.html.

## Phase 7: Tests und Abschluss

- [ ] T020 Playwright-E2E: Login-Rücksprung und jede Deep-Link-Form (SC-001); Screenshot-Smoke des Pilot-Boards (SC-004) bei 1440×900 und 390×844.
- [ ] T021 Alles grün (`pnpm -r test`, Build). `docker build` nur, wenn Docker verfügbar ist; sonst im Bericht vermerken. README-Statusmatrix: Dashboard-API, Dashboard-Web und Deployment aktualisieren.
