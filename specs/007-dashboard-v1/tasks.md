# Tasks: Dashboard v1

**Input**: [spec.md](spec.md), [plan.md](plan.md), Spec 002 (Contracts), [../../docs/architecture.md](../../docs/architecture.md)

## Phase 1: Setup

- [X] T001 `apps/dashboard-api` und `apps/dashboard-web` als Workspace-Pakete. Den Mock `server.js` entfernen. Abhängigkeit auf `@sak/contracts` (workspace).
  - Anmerkung: Die API wird mit esbuild gebündelt (`scripts/build.mjs`) statt mit `tsc`, weil `@sak/contracts` TypeScript-Quellen exportiert. `tsc` läuft als `lint` (Typprüfung). Paketnamen: `@sak/dashboard-api`, `@sak/dashboard-web`.
- [X] T002 [P] Vite, Tailwind und shadcn-Grundgerüst; Dark Mode; Hash-Router auf Basis der Deep-Link-Helfer.
  - Anmerkung: Tailwind v4 (`@tailwindcss/vite`), daher entfallen `tailwind.config.ts` und `postcss.config.js`; die Tokens stehen in `src/index.css`. Die shadcn-Bausteine sind im shadcn-Stil von Hand unter `src/components/ui` eingecheckt (new-york, zinc).

## Phase 2: Grundlagen API

- [X] T003 `env.ts` (Pflicht-Secrets), `db.ts` und `migrations.ts` (WAL, Schema aus plan.md).
- [X] T004 `auth/password.ts` (scrypt), `auth/session.ts` (HMAC-Cookie), `auth/rate-limit.ts`, Login-Sperre. `cli/hash-password.ts`.
  - Anmerkung: Der Passwort-Hash hat das Format `scrypt:N:r:p:salt:hash` (base64url, ohne `$`), damit er ohne Escaping in `.env`/Compose steht. Das Passwort wird nie per Argument übergeben, nur interaktiv oder über stdin (mindestens 12 Zeichen). Die Login-Sperre zählt jeden Versuch vorab als Fehlversuch (Schutz gegen parallele Versuche) und löscht die Einträge bei Erfolg.
- [X] T005 `app.ts` mit Fehlerbehandlung (JSON-Fehler, kein Stacktrace nach außen), `/healthz`, Auth-Routen und Auth-Middleware.
  - Anmerkung: Zusätzlich gesetzt: Sicherheits-Header inkl. CSP, `Cache-Control: no-store` für die API und eine Origin-Prüfung für schreibende Requests (zusätzlich zu SameSite=Strict). Mit dieser Phase wurde `app.ts` erst committet, weil es alle Routen einbindet.

## Phase 3: US4 – Ingest

- [X] T006 `services/projects.ts` und `cli/project.ts` (add, list, rotate, remove; Schlüssel einmalig ausgeben).
  - Anmerkung: Der Projekt-Schlüssel hat das Format `sak_<43 Zeichen base64url>` (256 Bit). Die Admin-Routen (`routes/admin.ts`, T016 Backend) nutzen denselben Service und liegen deshalb hier.
- [X] T007 `routes/ingest.ts` und `services/ingest.ts` gemäß Spec FR-004 und FR-006, mit Größenlimit 2 MB.
  - Anmerkung: Das Projekt ergibt sich aus dem Bearer-Schlüssel (Vergleich der SHA-256-Hashes mit allen Projekten in konstanter Zeit, ohne frühen Abbruch). Ist `project` in der Ingest-Hülle ein anderes Projekt, folgt 403 `project mismatch`; bei Events im Batch wird nur das betroffene Event abgelehnt (`rejected[]`). Ein veraltetes oder gleich altes Board ergibt `board_accepted: false` ohne `rejected`-Eintrag (Wiederholungen aus der Outbox sind normal); ein ungültiges oder fremdes Board ergibt zusätzlich einen `rejected`-Eintrag `board: …`. Zusätzlich zum Projekt-Limit (60/min) gilt ein Limit von 30 fehlgeschlagenen Authentifizierungen pro Minute und IP.
- [X] T008 `services/retention.ts` (täglich und beim Start).
  - Anmerkung: Die Frist gilt für den Event-Zeitstempel `ts`, nicht für den Empfangszeitpunkt.
- [X] T009 Vertragstests für Ingest (SC-002).

## Phase 4: US1–US3 – Lese-API

- [X] T010 `routes/meta.ts`, `routes/read.ts` und `services/portfolio.ts`, `services/runs.ts`.
  - Anmerkung: `GET /api/projects/:key/events` liefert ohne `since` die neuesten `limit` Events (aufsteigend), mit `since` die ersten `limit` Events danach. Das Portfolio liefert zusätzlich `escalation` (eskalierter Lauf samt Grund) und `warnings` (`stale`, `idle`, `no_push_24h`; diese Warnungsbegriffe sind nicht Teil des Vokabulars). Das Alter für `no_push_24h` bemisst sich ab `last_ingest_at`, bei Projekten ohne Einlieferung ab Anlage.
- [X] T011 Tests für die Lese-API mit dem Pilot-Board-Beispiel aus `packages/contracts/examples/valid/`.
  - Anmerkung: Die Beispiel-Ingest-Requests der Contracts enthalten nur 2 Events bzw. kein Event; die Lauf-Events zu Lauf 088 leitet der Test deshalb aus den Stationen des Pilot-Boards ab (`pilotEvents()`).

## Phase 5: UI

- [X] T012 Login mit Rücksprung zur Ziel-URL.
  - Anmerkung: Bei fehlender Session erscheint die Anmeldung unter der angefragten URL; der Hash bleibt unverändert, daher rendert nach dem Login dieselbe Route (Rücksprung). Zusätzlich wird `#/login?next=<hash>` unterstützt (nur interne Ziele).
- [X] T013 Portfolio: Projektkarten, Warnungen, Hervorhebung bei Eskalation.
  - Anmerkung: Die Warnungstexte „Lauf inaktiv“ und „Kein Push seit über 24 Std.“ sind UI-Texte, weil das Vokabular dafür keine Werte kennt; „Lauf hängt“ stammt aus `attention_kind.stale_run`.
- [X] T014 Projekt: Tabs board, runs, attention, conflicts mit `?tab=`-Sync; Kennzahlen-Kacheln, Stationsspalten, „Mensch prüft“-Spalte, Agenten-Panel, Ticker, 2 Diagramme.
  - Anmerkung: Die Stationsspalten (ab 900 px) füllen die Breite mit `auto-fill` und brechen bei Bedarf in eine zweite Zeile um, statt horizontal zu scrollen; unter 900 px stehen sie untereinander. „Mensch prüft / entscheidet“ ist die erste Spalte und zeigt die `attention`-Einträge; wartende und blockierte Specs tragen zusätzlich ein Badge in ihrer Stationsspalte. Zurückgestellte Specs stehen eingeklappt unter dem Board. Der Tab `operator` aus `docs/ui/dashboard-concept.md` entfällt; es gelten die Tabs aus Spec 002 (`attention`).
- [X] T015 Lauf-Ansicht: Runden, Stationen, Urteile, Eskalationen, Event-Log.
  - Anmerkung: Ist der Lauf nicht mehr im Board (mehr als 20 Läufe), werden nur die gespeicherten Events gezeigt.
- [X] T016 Admin: Projekte verwalten.
- [X] T017 Polling alle 10 s, sichtbar-abhängig; „zuletzt aktualisiert“; Fehler- und Leerzustände; Labels über Contracts, unbekannte Werte als „unbekannt (wert)“.

## Phase 6: Deploy

- [X] T018 `deploy/dashboard/Dockerfile` (Multi-Stage, non-root, Healthcheck), `compose.snippet.yml` (externes Netz `${SAK_EDGE_NETWORK:-edge}`), `caddy.example`, `README.md` (Betrieb, Secrets, Projekt anlegen).
  - Anmerkung: Das Dockerfile wurde nicht gebaut (Docker ist auf dieser Maschine nicht installiert). Die Laufzeit-Stage installiert nur `better-sqlite3` per npm; alles andere steckt im esbuild-Bundle. Die Variablen des alten Snippets (`SQLITE_PATH`, `DASHBOARD_DEFAULT_VIEW`) entfallen, es gelten die Namen aus Spec FR-001.
- [X] T019 `server.ts` liefert die statische UI aus, mit SPA-Fallback auf index.html.
  - Anmerkung: Der Code liegt seit Phase 4 in `static.ts`/`app.ts`; Tests kamen hier dazu (`test/static.test.ts`). Pfade ohne Dateiendung fallen auf `index.html` zurück, fehlende Dateien mit Endung ergeben 404.

## Phase 7: Tests und Abschluss

- [X] T020 Playwright-E2E: Login-Rücksprung und jede Deep-Link-Form (SC-001); Screenshot-Smoke des Pilot-Boards (SC-004) bei 1440×900 und 390×844.
  - Anmerkung: Ausführen mit `pnpm -r build` und danach `pnpm --filter @sak/dashboard-web e2e` (startet den Server auf Port 3100 mit frischer DB und Test-Secrets). Die E2E-Tests laufen nicht in `pnpm -r test` und noch nicht in der CI (dort fehlt die Browser-Installation). Screenshots: `apps/dashboard-web/e2e/screenshots/` (nicht eingecheckt).
- [X] T021 Alles grün (`pnpm -r test`, Build). `docker build` nur, wenn Docker verfügbar ist; sonst im Bericht vermerken. README-Statusmatrix: Dashboard-API, Dashboard-Web und Deployment aktualisieren.
  - Anmerkung: `docker build` nicht ausgeführt (Docker nicht installiert). SC-003 (Start unter 5 s, RAM unter 150 MB) wurde nicht gemessen.
