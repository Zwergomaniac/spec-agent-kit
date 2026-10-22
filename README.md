# spec-agent-kit

> **Status:** v1 der Specs 001 bis 007 und Spec 009 (lokale Bedienung und Betrieb) sind umgesetzt, ebenso die Robustheits-Härtung aus dem ImmoAgent-Trial (Spec 011, Kit 0.2.0) sowie die Autonomie-Stufen für Merge, Push und Deploy (Spec 012, Kit 0.3.0). Der Betrieb in Claude Cloud (Spec 013, Kit 0.4.0) ist umgesetzt, die manuelle Abnahme (SC-003) durch den Betreiber steht aus. Mehrere benannte Deploy-Wege (GitHub-Workflow und lokal, Spec 014, Kit 0.5.0) sind umgesetzt. Spec 015 ist im Repo-Code weitgehend umgesetzt: Init, Upgrade, Config-Check und Doctor unterscheiden nun zwischen `claude` und `copilot`, inklusive Copilot-Artefakten unter `.github/copilot/` sowie VS-Code-Settings/Tasks. Die echte Import-/Installationssimulation in einem separaten Zielprojekt steht bewusst noch aus. Der Pilot in einem echten Projekt (Spec 008, AI-Forge) steht ebenfalls aus. Offene Punkte: [docs/follow-ups.md](docs/follow-ups.md).

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
| Pipeline-Engine (`sak run`, `sak hook`, `sak event`) | implementiert | Zustandsmaschine mit `paused`, Wächter, Urteile, `combine`, `merge` ohne Push, `push` nach Autonomie-Stufe, Übernahme verwaister Läufe, Nur-Prüfung, Hooks; Spec 003. Dazu Spec 011: `run cleanup` (Links), Worktree-Erkennung, Lauf-Kontext nach dem Kompaktieren (`hook session-start`) | `packages/engine/src/spec_agent_kit/pipeline` |
| Rollen, Agents, Orchestrator-Skill | implementiert | Claude- und Copilot-Vorlagen für Builder, Code-, UI-, Sicherheits-Prüfer und Doku. Claude nutzt `.claude/*` plus `settings.fragment.json`; Copilot nutzt `.github/copilot/*` | `packages/agent-blueprint/templates/claude`, `packages/agent-blueprint/templates/copilot` |
| Projektkonfiguration | implementiert | `.spec-agent/config.yml` (`sak.config/1`), `sak config check` und `show`; Spec 004. Mit `agent_environment: claude|copilot` und env-spezifischer Agent-Prüfung. Die AI-Forge-Beispielwerte sind ungeprüft | `packages/engine/src/spec_agent_kit/config`, `packages/agent-blueprint/templates/config` |
| Init, Upgrade, Doctor | implementiert | Plan vor `--apply` (mit allen Allow- und Deny-Regeln), `--format json\|text`, `.sak-new` statt Überschreiben, Lockfile mit `settings_allow`, additiver Claude-Settings-Merge, env-spezifische Artefaktsätze für `claude` und `copilot`, Copilot-Hook-Ersatz über `.vscode/tasks.json`, vendorte Engine, Vorschläge aus der Projekt-Erkennung, `doctor --probe-commands`; Spec 005, 011, 015. Noch nie gegen ein echtes separates Zielprojekt importiert/getestet | `packages/engine/src/spec_agent_kit/install` |
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

uv run --project packages/engine pytest      # nur Python: die ganze Suite in einem Lauf (nicht mehr in Teilen)
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

- `--agent-environment claude|copilot`: aktiv verwaltete Agent-Umgebung wählen (Default `claude`).
- `--no-ui`: `ui_review` bleibt aus (kein Web-UI im Projekt).
- `--base-branch`, `--dashboard-url`, `--test-fast`, `--test-full`, `--lint` (Befehle wiederholbar).
- `--allow-dirty`, `--no-sync` (überspringt `uv sync` im Engine-Ordner).

Das Kit überschreibt nie still: geänderte Dateien landen als `<datei>.sak-new` daneben. `.spec-agent/config.yml` wird einmal angelegt und danach nie angefasst.

Später aktualisieren: `sak upgrade <zielpfad>` zeigt den Plan, `--apply` setzt ihn um (Ersetzen, Löschen, Konflikte anhand `.spec-agent/lock.json`; neue Config-Schlüssel werden gemeldet, nicht eingetragen).

Für `claude` installiert das Kit Agent-Artefakte unter `.claude/` und merged in `.claude/settings.json`. Für `copilot` installiert es Agent-Artefakte unter `.github/copilot/` sowie `.vscode/settings.json` und `.vscode/tasks.json`; die Hook-Funktion wird dort über native VS-Code-Tasks angenähert.

Geführt geht es im Kit-Repo mit dem Skill `/sak-init`: er stellt die Fragen, zeigt den Plan und wendet ihn erst nach Bestätigung an.

## Im Zielprojekt arbeiten

Im Zielprojekt steht die Engine unter `.spec-agent/engine`. Empfohlener Aufruf ist der Starter, den Init und Upgrade mit installieren: `.spec-agent\sak` (Windows, `sak.cmd`) bzw. `.spec-agent/sak` (POSIX). Er findet uv auch ohne PATH (Reihenfolge: `SAK_UV`, PATH, bekannte Installationsorte) und reicht den Exit-Code von `sak` durch. Abkürzung hier: `SAK` = der Starter (gleichwertig: `uv run --project .spec-agent/engine sak`). Die Hooks in `.claude/settings.json` rufen ebenfalls den POSIX-Starter auf (`sh "$CLAUDE_PROJECT_DIR/.spec-agent/sak" hook …`), damit sie auch ohne uv im PATH der Sitzung laufen; `sak doctor` prüft das mit einer echten Hook-Probe, `sak upgrade` stellt alte Einträge um.

```sh
# Pipeline: im Claude-Code-Chat, erst nach ausdrücklichem „umsetzen“ für genau diese Spec
/sak-pipeline <spec>          # auch: --release | --return | --abort | --pause | --resume <spec>

SAK run list [--all]          # offene (mit --all auch beendete) Läufe
SAK run show <lauf>           # ein Lauf
SAK run push <lauf>           # Basis-Branch eines gemergten Laufs pushen (nur bei autonomy.push: after_merge)
SAK config check              # Konfiguration prüfen
SAK board --text              # Kurzfassung des Boards (höchstens 40 Zeilen); --json ist der Standard
SAK board serve [--port N] [--open]  # lokale Ansicht auf 127.0.0.1, ohne Netz; --open startet den Browser
SAK push                      # Events und Board ans Dashboard senden (--background, --quiet)
```

`board serve` probiert ohne `--port` zuerst 5192, bei Belegung die nächsten freien Ports bis 5212. Mit `--port` gilt genau dieser Port (belegt: Exit 2).

### Autonomie-Stufen

Was der Orchestrator nach einem Lauf in `approved` selbst tun darf, steht im Block `autonomy` der `.spec-agent/config.yml`. Nur der Betreiber ändert ihn. Die Defaults sind streng.

| Schlüssel | Werte (Default zuerst) | Wirkung |
| --- | --- | --- |
| `autonomy.push` | `manual`, `after_merge` | `after_merge`: Der Orchestrator führt nach dem Merge ohne Rückfrage `sak run push <lauf>` aus. `manual`: Der Betreiber pusht selbst; `sak run push` lehnt mit Hinweis auf die Config ab. |
| `autonomy.deploy` | `after_approval`, `never` | `after_approval`: Der Orchestrator deployt nur nach ausdrücklichem OK im Chat. `never`: Der Orchestrator deployt nie, nur der Betreiber. |
| `autonomy.remote` | `origin` | Ziel des Pushs. |

Merge nach `approved` läuft immer automatisch (`sak run merge`). `sak run push` führt ausschließlich `git push <remote> <basis>:<basis>` aus, ohne `--force`, ohne Tags, mit 60 s Zeitlimit und ohne Zugangsdaten in der Ausgabe. Es lehnt ab, wenn der Lauf nicht `merged` ist, ein anderer Branch als der Basis-Branch ausgecheckt ist, der Basis-Branch den Merge-Commit des Laufs nicht enthält oder die Stufe `manual` gilt. Auch ein Marker-Commit (`deploy(NNN): …`) nach dem Merge desselben Laufs lässt sich so pushen. Ist das Remote weiter (non-fast-forward), wird weder gemergt noch rebased: Der Befehl lehnt ab und der Lauf bekommt einen Aufmerksamkeitseintrag „Push abgelehnt“ (Art `escalation`, Gate `release`), bis ein späterer Push gelingt. Erfolgreiche Pushes erscheinen als Ereignis `run.pushed` (Label „Gepusht“) und als Zusatz „gepusht“ am Lauf. Die Deny-Regel `git push` in den Settings bleibt bestehen: Direkte Pushes und Pushes durch Subagents sind weiterhin gesperrt. Fachliche Eskalationen und das Rundenlimit stoppen den Lauf unverändert bis `release`.

### Dashboard anbinden

```sh
SAK dashboard connect --url https://dashboard.example.org                    # zeigt nur den Plan
SAK dashboard connect --url https://dashboard.example.org --key-stdin --yes  # Schlüssel von stdin lesen, Plan umsetzen
SAK dashboard status                                                         # Stand der Anbindung
```

`connect` trägt `dashboard.url` in die Config ein, schreibt den Projekt-Schlüssel nach `.spec-agent/dashboard.key` und löst einen Test-Push aus. Weitere Optionen: `--force` ersetzt eine vorhandene `dashboard.key`, `--no-test-push` überspringt den Test-Push. Schlägt der Test-Push fehl, endet `connect` mit Exit 1; Config und Schlüssel bleiben dann trotzdem geschrieben. `http://` ist nur für localhost erlaubt. Der Schlüssel erscheint nie in der Ausgabe.

Für den Push braucht das Projekt `dashboard.url` in der Config und den Projekt-Schlüssel in der Umgebungsvariable `SAK_DASHBOARD_TOKEN` oder in der Datei `.spec-agent/dashboard.key` (gitignoriert). Bei `push: auto` startet der Push nach Hooks und Run-Befehlen im Hintergrund und blockiert nie die Pipeline.

### Kit in Claude Cloud

In einer Claude-Code-Cloud-Sitzung fehlt die gitignorierte `.spec-agent/dashboard.key`, und ausgehende Verbindungen laufen über einen Proxy mit Allowlist. Ausführlich: [docs/cloud.md](docs/cloud.md). Kurzfassung:

1. Netzzugriff: „Network access“ auf Custom stellen und den Dashboard-Host eintragen, oder ein Network Secret für den Host anlegen (umgeht die Allowlist).
2. Network Secret (empfohlen): Host des Dashboards, Typ Bearer, Wert = Projekt-Schlüssel. In der Umgebung `SAK_DASHBOARD_AUTH=proxy` setzen (oder `dashboard.auth: proxy` in der Config, z. B. via `sak dashboard connect --url … --auth proxy --yes`). Im Proxy-Modus sendet das Kit nie einen eigenen `Authorization`-Header.
3. Alternative: `SAK_DASHBOARD_TOKEN` in der Umgebung. Achtung: Umgebungsvariablen sind für den Agenten und alle Nutzer der Umgebung lesbar.
4. Für `autonomy.push: after_merge` braucht die Sitzung Push-Rechte auf GitHub (Branches ja, Tags und Löschen nein). Empfehlung: Branch-Protection bzw. Rulesets.
5. Hooks und Board laufen im Container (lokale Monitore sehen nichts). Das Ergebnis liegt erst nach einem Push auf GitHub.

`sak doctor` und `sak dashboard status` erklären typische Cloud-Fehler (Proxy lehnt den Host ab, fehlendes Network Secret, TLS hinter dem Proxy).

**Deploy-Wege (Spec 014).** `deploy.methods` in der Config benennt mehrere Wege, `deploy.default` wählt den Standard („deployen“; „deployen lokal“ nimmt den Weg `local`). Je Weg: `command` (mit `{spec}`), `marker: agent|workflow` (wer den Marker `deploy(NNN)` setzt) und `local_only` (in Claude Cloud abgelehnt). `deploy.command` allein bleibt als Weg `default` gültig. `sak deploy plan [--method <name>] <spec>` zeigt Weg, Befehl, Marker-Modus und Erlaubnis als JSON, ohne etwas auszuführen; `SAK_ENVIRONMENT=cloud|local` übersteuert die Umgebungserkennung. Einrichtung des Workflows: [docs/howto/github-actions-deploy.md](docs/howto/github-actions-deploy.md).

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
- [docs/cloud.md](docs/cloud.md) – Betrieb in Claude Cloud (Proxy-Modus, Network Secret, Diagnose)
- [docs/follow-ups.md](docs/follow-ups.md) – offene Punkte
- [docs/ui/dashboard-concept.md](docs/ui/dashboard-concept.md) – Ansichten und URL-Modell
- [docs/adr/0001-framework-grundsatzentscheidungen.md](docs/adr/0001-framework-grundsatzentscheidungen.md) – Grundsatzentscheidungen
- [docs/architecture-vision.md](docs/architecture-vision.md) – Protokoll der Stack-Beratung (Historie, nicht verbindlich)
- [deploy/dashboard/README.md](deploy/dashboard/README.md) – Betrieb des Dashboards
- [.specify/memory/constitution.md](.specify/memory/constitution.md) – Constitution
- [specs/](specs/) – Specs 001 bis 007 und 009 sind umgesetzt, 008 (Pilot) ist ein Entwurf

## Bekannte Lücken

Kurz: Pilot in AI-Forge, CI auf einem Remote, E2E in der CI, Parallelbetrieb und Plugins. Die vollständige Liste mit Herkunft und Vorschlag steht in [docs/follow-ups.md](docs/follow-ups.md).
