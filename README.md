# spec-agent-kit

> **Status:** v1 der Specs 001 bis 007 und Spec 009 (lokale Bedienung und Betrieb) sind umgesetzt. Der Pilot in einem echten Projekt (Spec 008, AI-Forge) steht aus. Offene Punkte: [docs/follow-ups.md](docs/follow-ups.md).

Ein gemeinsames Mixed Repo für zwei eng gekoppelte Systeme:

1. **Spec Agent Kit** – Vorlagen (Blueprint), Init-/Upgrade-CLI, Agent-Skills, Contracts und Pipeline-Engine (`sak`) für Spec-getriebene Agentenarbeit.
2. **Dashboard** – Mehrprojekt-Admin-UI (API + Web) für Projekte, Specs, Läufe, Agentenstatus und Betreiber-Gates.

Ursprung ist die Pipeline aus dem Projekt ImmoAgent (Specs 092 und 093, nur gelesen), generalisiert für beliebige Zielprojekte. Beide Teile sind absichtlich gemeinsam versioniert, weil Änderungen an Pipeline, Events und Rollen fast immer die Dashboard-Darstellung berühren.

## Kernentscheidungen

- `packages/contracts` ist die einzige Quelle für Events, Board-Dokument, Projektregistrierung und Statusvokabular.
- Das Dashboard speichert nur Metadaten, niemals Code, Prompts, Tokens oder Secrets.
- Startansicht ist das Portfolio, jede Ansicht ist per URL direkt verlinkbar.
- Engine im Zielprojekt: Python über uv (vendort unter `.spec-agent/engine`). Dashboard: TypeScript (Hono, React/Vite, Tailwind/shadcn, SQLite).
- Caddy läuft extern und wird hier nicht verwaltet.
- Details: [docs/architecture.md](docs/architecture.md), [ADR 0001](docs/adr/0001-framework-grundsatzentscheidungen.md), [Constitution](.specify/memory/constitution.md).

## Status je Baustein

Werte: **implementiert** (Code und Tests vorhanden), **teilweise**, **Konzept** (nur beschrieben), **fehlt**.

| Baustein | Status | Anmerkung | Ort |
| --- | --- | --- | --- |
| Contracts (Schemas, Vokabular, Labels, Deep Links) | implementiert | JSON Schema, generierte Zod-Typen, Python-Validierung; Specs 001, 002 | `packages/contracts`, `packages/engine/src/spec_agent_kit/contracts.py` |
| Pipeline-Engine (`sak run`, `sak hook`, `sak event`) | implementiert | Zustandsmaschine mit `paused`, Wächter, Urteile, `combine`, `merge` ohne Push, Übernahme verwaister Läufe, Nur-Prüfung, Hooks; Spec 003 | `packages/engine/src/spec_agent_kit/pipeline` |
| Rollen, Agents, Orchestrator-Skill | implementiert | Vorlagen für Builder, Code-, UI-, Sicherheits-Prüfer und Doku, Skill `sak-pipeline`, `settings.fragment.json` | `packages/agent-blueprint/templates/claude` |
| Projektkonfiguration | implementiert | `.spec-agent/config.yml` (`sak.config/1`), `sak config check` und `show`; Spec 004. Die AI-Forge-Beispielwerte sind ungeprüft | `packages/engine/src/spec_agent_kit/config`, `packages/agent-blueprint/templates/config` |
| Init, Upgrade, Doctor | implementiert | Plan vor `--apply`, `.sak-new` statt Überschreiben, Lockfile, additiver Settings-Merge, vendorte Engine; Spec 005. Noch nie gegen ein echtes Zielprojekt gelaufen | `packages/engine/src/spec_agent_kit/install` |
| Skill `/sak-init` | implementiert | geführte Einrichtung, nur im Kit-Repo; die Logik steckt im CLI | `.claude/skills/sak-init` |
| Collector, lokales Board, Push | implementiert | `sak board`, `sak board serve`, ausfallsicherer `sak push`; Spec 006 | `packages/engine/src/spec_agent_kit/board`, `.../push` |
| Dashboard-API | implementiert | Hono + SQLite, Admin-Login, Ingest mit Contracts-Validierung, Lese-API, Retention, Projekt-CLI; Spec 007 | `apps/dashboard-api` |
| Dashboard-Web | implementiert | Portfolio, Projekt (Tabs), Lauf-Ansicht, Admin, Login, Dark Mode, Deep Links. Der Tab `conflicts` zeigt nur einen Hinweis | `apps/dashboard-web` |
| Deployment (Container) | implementiert | Image gebaut und produktiv seit 2026-10-20, per Skript aktualisiert (`deploy-vps.sh`, Spec 009); Dockerfile, Compose-Snippet, Caddy-Beispiel; Leerlauf-RAM gemessen (18 MB) | `deploy/dashboard` |
| Lokale Bedienung (Starter, `board serve`, `dashboard connect`, `dashboard:local`) | implementiert | Starter `.spec-agent/sak` und `sak.cmd`, Port-Ausweichen, Anbindung in einem Befehl, lokales Dashboard ohne Docker, Portfolio-Karte als Link; Spec 009 | `packages/engine`, `apps/dashboard-api/scripts`, `apps/dashboard-web` |
| Tests | implementiert | vitest (TS), pytest (Engine), Smoke-Test für Init/Upgrade, API-Vertragstests, Playwright-E2E (lokal) | `**/test`, `packages/engine/tests`, `apps/dashboard-web/e2e` |
| CI | teilweise | Workflow vorhanden (TS, Python, Smoke-Test; Ubuntu und Windows), noch nie auf einem Remote gelaufen; E2E nicht enthalten | `.github/workflows/ci.yml` |
| Pilot in AI-Forge | fehlt | Spec 008 ist ein Entwurf | `specs/008-pilot-ai-forge` |
| Parallelbetrieb (Worktrees, Konflikt-Radar) | Konzept | nur nicht verbaut (Constitution VIII); Integrator-Rolle ist reserviert | – |
| Plugins (graphify, impeccable, Queue/Blocker) | Konzept | `plugins: []` in der Config ist nur reserviert | – |
| Verteilung per `uvx` | fehlt | Rollout heute nur aus dem Kit-Repo | – |

## Schnellstart lokal: Dashboard ohne Docker

Voraussetzungen wie unten (Node 22+, pnpm 10). Nach `pnpm install`:

```sh
pnpm dashboard:local                                     # baut bei Bedarf, startet auf http://127.0.0.1:3000 (nur Loopback)
pnpm dashboard:project add mein-projekt "Mein Projekt"   # Projekt anlegen; der Schlüssel erscheint genau einmal
pnpm dashboard:project list                              # auch: rotate <key>, remove <key>
```

`--rebuild` erzwingt einen neuen Build. Den Schlüssel gibt man danach an `sak dashboard connect` (siehe unten).

## Schnellstart: am Kit entwickeln

Voraussetzungen: Node 22+, pnpm 10, Python 3.11+ und uv.

```sh
pnpm install
uv sync --project packages/engine

pnpm test             # vitest in allen TS-Paketen + pytest der Engine (pytest dauert etwa 5 Minuten)
pnpm lint             # tsc je Paket + ruff
pnpm build            # Contracts, API (esbuild-Bundle), Web

uv run --project packages/engine pytest      # nur die Python-Tests
pnpm --filter @sak/dashboard-web e2e         # Playwright-E2E, braucht vorher `pnpm build`

pnpm contracts:gen    # Zod-Typen und Python-Schema-Kopie aus packages/contracts/schema erzeugen
pnpm contracts:check  # gen + Diff-Prüfung (schlägt fehl, wenn Generiertes nicht eingecheckt ist)
```

Die CLI im Kit-Repo: `uv run --project packages/engine sak --help`.

## Ein Projekt einbinden

Das Zielprojekt muss ein sauberes Git-Repo (Git-Wurzel) mit spec-kit sein. Alle Befehle laufen im Kit-Repo.

```sh
# 1. Plan ansehen (schreibt nichts)
uv run --project packages/engine sak init <zielpfad> --key mein-projekt --name "Mein Projekt"

# 2. Plan umsetzen
uv run --project packages/engine sak init <zielpfad> --key mein-projekt --name "Mein Projekt" --apply

# 3. Gesundheitscheck
uv run --project packages/engine sak doctor <zielpfad>
```

Nützliche Optionen von `init`:

- `--no-ui`: `ui_review` bleibt aus (kein Web-UI im Projekt).
- `--base-branch`, `--dashboard-url`, `--test-fast`, `--test-full`, `--lint` (Befehle wiederholbar).
- `--allow-dirty`, `--no-sync` (überspringt `uv sync` im Engine-Ordner).

Das Kit überschreibt nie still: geänderte Dateien landen als `<datei>.sak-new` daneben. `.spec-agent/config.yml` wird einmal angelegt und danach nie angefasst.

Später aktualisieren: `sak upgrade <zielpfad>` zeigt den Plan, `--apply` setzt ihn um (Ersetzen, Löschen, Konflikte anhand `.spec-agent/lock.json`; neue Config-Schlüssel werden gemeldet, nicht eingetragen).

Geführt geht es im Kit-Repo mit dem Skill `/sak-init`: er stellt die Fragen, zeigt den Plan und wendet ihn erst nach Bestätigung an.

## Im Zielprojekt arbeiten

Im Zielprojekt steht die Engine unter `.spec-agent/engine`. Empfohlener Aufruf ist der Starter, den Init und Upgrade mit installieren: `.spec-agent\sak` (Windows, `sak.cmd`) bzw. `.spec-agent/sak` (POSIX). Er findet uv auch ohne PATH (Reihenfolge: `SAK_UV`, PATH, bekannte Installationsorte) und reicht den Exit-Code von `sak` durch. Abkürzung hier: `SAK` = der Starter (gleichwertig: `uv run --project .spec-agent/engine sak`). Die Hooks in `.claude/settings.json` rufen ebenfalls den POSIX-Starter auf (`sh "$CLAUDE_PROJECT_DIR/.spec-agent/sak" hook …`), damit sie auch ohne uv im PATH der Sitzung laufen; `sak doctor` prüft das mit einer echten Hook-Probe, `sak upgrade` stellt alte Einträge um.

```sh
# Pipeline: im Claude-Code-Chat, erst nach ausdrücklichem „umsetzen“ für genau diese Spec
/sak-pipeline <spec>          # auch: --release | --return | --abort | --pause | --resume <spec>

SAK run list [--all]          # offene (mit --all auch beendete) Läufe
SAK run show <lauf>           # ein Lauf
SAK config check              # Konfiguration prüfen
SAK board --text              # Kurzfassung des Boards (höchstens 40 Zeilen); --json ist der Standard
SAK board serve [--port N] [--open]  # lokale Ansicht auf 127.0.0.1, ohne Netz; --open startet den Browser
SAK push                      # Events und Board ans Dashboard senden (--background, --quiet)
```

`board serve` probiert ohne `--port` zuerst 5192, bei Belegung die nächsten freien Ports bis 5212. Mit `--port` gilt genau dieser Port (belegt: Exit 2).

### Dashboard anbinden

```sh
SAK dashboard connect --url https://dashboard.example.org                    # zeigt nur den Plan
SAK dashboard connect --url https://dashboard.example.org --key-stdin --yes  # Schlüssel von stdin lesen, Plan umsetzen
SAK dashboard status                                                         # Stand der Anbindung
```

`connect` trägt `dashboard.url` in die Config ein, schreibt den Projekt-Schlüssel nach `.spec-agent/dashboard.key` und löst einen Test-Push aus. Weitere Optionen: `--force` ersetzt eine vorhandene `dashboard.key`, `--no-test-push` überspringt den Test-Push. Schlägt der Test-Push fehl, endet `connect` mit Exit 1; Config und Schlüssel bleiben dann trotzdem geschrieben. `http://` ist nur für localhost erlaubt. Der Schlüssel erscheint nie in der Ausgabe.

Für den Push braucht das Projekt `dashboard.url` in der Config und den Projekt-Schlüssel in der Umgebungsvariable `SAK_DASHBOARD_TOKEN` oder in der Datei `.spec-agent/dashboard.key` (gitignoriert). Bei `push: auto` startet der Push nach Hooks und Run-Befehlen im Hintergrund und blockiert nie die Pipeline.

## Dashboard betreiben und entwickeln

Betrieb (Image, Umgebungsvariablen, Secrets, Projekt anlegen, Caddy): [deploy/dashboard/README.md](deploy/dashboard/README.md).

Update des laufenden Dashboards auf dem VPS (deployt wird `HEAD` eines sauberen Arbeitsstands; Zugangsdaten in der gitignorierten `deploy/dashboard/vps.env`, Vorlage `vps.env.example`):

```sh
deploy/dashboard/deploy-vps.sh --dry-run   # zeigt alle Schritte, führt nichts aus
deploy/dashboard/deploy-vps.sh             # Image auf dem VPS bauen, Dienst neu starten, auf healthy warten
deploy/dashboard/deploy-vps.sh --prune     # zusätzlich den Build-Cache aufräumen
```

Lokale Entwicklung (API auf Port 3000, UI mit Vite-Proxy auf die API):

```sh
pnpm build   # einmal: erzeugt auch apps/dashboard-api/dist/cli/hash-password.js
# Passwort-Hash erzeugen (Passwort wird abgefragt, mindestens 12 Zeichen):
pnpm --filter @sak/dashboard-api hash-password

# Terminal 1 (PowerShell: $env:NAME = "wert"; Bash: export NAME=wert)
#   NODE_ENV=development  SAK_ADMIN_PASSWORD_HASH=<hash>  SAK_SESSION_SECRET=<mindestens 32 Zeichen>  SAK_DB_PATH=<datei>
pnpm --filter @sak/dashboard-api dev

# Terminal 2
pnpm --filter @sak/dashboard-web dev
```

Ein Projekt legt man in der UI unter `#/admin` oder per `pnpm --filter @sak/dashboard-api project add <key> <name>` an (nach `pnpm build`; der Schlüssel erscheint genau einmal).

## Repo-Layout

```text
packages/
  contracts/        Schemas, Vokabular, Labels, generierte Zod-Typen, Deep Links (@sak/contracts)
  engine/           Python-Paket spec_agent_kit mit CLI `sak` (uv-Projekt)
  agent-blueprint/  Vorlagen für Zielprojekte (Agents, Skills, Config, Settings-Fragment)
apps/
  dashboard-api/    Hono + SQLite (@sak/dashboard-api)
  dashboard-web/    React + Vite + Tailwind/shadcn (@sak/dashboard-web)
deploy/dashboard/   Dockerfile, Compose-Snippet, Caddy-Beispiel, Betriebs-README
docs/               Architektur, ADR, UI-Konzept, offene Punkte
specs/              spec-kit-Artefakte 001 bis 009 (Dogfooding)
.claude/skills/     spec-kit-Skills und `sak-init`
.specify/           spec-kit-Upstream (Constitution unter memory/)
```

## Dokumente

- [docs/architecture.md](docs/architecture.md) – Architektur, Laufzeitregeln, Umsetzungsstand und Abweichungen vom Plan
- [docs/follow-ups.md](docs/follow-ups.md) – offene Punkte
- [docs/ui/dashboard-concept.md](docs/ui/dashboard-concept.md) – Ansichten und URL-Modell
- [docs/adr/0001-framework-grundsatzentscheidungen.md](docs/adr/0001-framework-grundsatzentscheidungen.md) – Grundsatzentscheidungen
- [docs/architecture-vision.md](docs/architecture-vision.md) – Protokoll der Stack-Beratung (Historie, nicht verbindlich)
- [deploy/dashboard/README.md](deploy/dashboard/README.md) – Betrieb des Dashboards
- [.specify/memory/constitution.md](.specify/memory/constitution.md) – Constitution
- [specs/](specs/) – Specs 001 bis 007 und 009 sind umgesetzt, 008 (Pilot) ist ein Entwurf

## Bekannte Lücken

Kurz: Pilot in AI-Forge, CI auf einem Remote, E2E in der CI, Parallelbetrieb und Plugins. Die vollständige Liste mit Herkunft und Vorschlag steht in [docs/follow-ups.md](docs/follow-ups.md).
