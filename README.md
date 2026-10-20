# spec-agent-kit

> **Status:** Frühes Gerüst. Der Pipeline-Kern wird aus ImmoAgent extrahiert (Specs unter specs/). Siehe Status-Matrix.

Ein gemeinsames Monorepo für zwei eng gekoppelte Systeme:

1. **Spec Agent Kit** – Blueprint, Init-Logik, Agent-Skill, Contracts und Pipeline-Bausteine für Spec-getriebene Agentenarbeit.
2. **Dashboard** – Mehrprojekt-Admin-UI zur Anzeige von Projekten, Specs, Runs, Agentenstatus, Konflikten und Betreiber-Gates.

## Produktidee

Dieses Repo ist absichtlich ein **Mixed Repo**. Blueprint und Dashboard werden gemeinsam entwickelt, weil strukturelle Änderungen an Pipeline, Events und Rollen fast immer Auswirkungen auf die Dashboard-Darstellung haben.

## Kernentscheidungen

- **Default-Landing-View:** Portfolio
- **Direkte Deep Links:** ja, per URL-Routing vorgesehen
- **Dashboard-Daten:** nur Metadaten, niemals Code, Prompts, Tokens oder Secrets
- **Persistenz:** SQLite für v1 und kleine Installationen
- **Auth:** einfacher Admin-Schutz für interne Nutzung
- **Reverse Proxy:** bestehender Caddy-Container außerhalb dieses Repos
- **Rollout in weitere Projekte:** Templates + `sak init`/`sak upgrade` + Skill `sak-init`
- **Engine-Laufzeit im Zielprojekt:** Python via uv; Dashboard: TypeScript (Hono, React/Vite, SQLite)

## Status je Baustein

| Baustein | Status | Ort |
| --- | --- | --- |
| Pipeline-Engine (Stationen, Urteile, Gates) | implementiert (`sak run`, `sak hook`, `sak event`: Läufe mit Lauf-ID, Zustandsmaschine mit `paused`, Wächter, Urteile, `combine`, `merge` ohne Push, Übernahme verwaister Läufe, Nur-Prüfung, Hooks; Spec 003, portiert aus ImmoAgent Spec 093) | packages/engine/src/spec_agent_kit/pipeline |
| Rollen-/Agent-Definitionen | implementiert (Vorlagen für Builder, Code-, UI- und Sicherheits-Prüfer, Doku, Orchestrator-Skill `sak-pipeline` und `settings.fragment.json`; die Installation ins Zielprojekt erledigt `sak init`, Spec 005) | packages/agent-blueprint/templates/claude |
| Contracts (Event-/Board-Vertrag, Statusvokabular) | implementiert (JSON Schema, Vokabular, Labels, generierte Zod-Typen, Python-Validierung, Deep-Link-Helfer; Specs 001 und 002) | packages/contracts, packages/engine/src/spec_agent_kit/contracts.py |
| Projektkonfiguration (`.spec-agent/config.yml`) | implementiert (Schema `sak.config/1`, Laden mit Defaults und Kern-Schutz, `sak config check` und `sak config show`, Vorlage und Beispiel-Configs für ImmoAgent und AI-Forge; Spec 004; die AI-Forge-Werte sind im Pilot zu prüfen) | packages/contracts/schema/config.schema.json, packages/engine/src/spec_agent_kit/config, packages/agent-blueprint/templates/config |
| Init-CLI (`sak init`) | ersetzt das alte Init-Skript, implementiert (Plan vor Apply, Validierung, `.sak-new` statt Überschreiben, additiver Settings-Merge, Lockfile `sak.lock/1`, vendorte Engine mit `uv sync`; Spec 005; Pilot gegen ein echtes Projekt steht aus, Spec 008) | packages/engine/src/spec_agent_kit/install |
| Upgrade-CLI (`sak upgrade`, `sak doctor`) | implementiert (Ersetzen, Löschen, Konflikte anhand des Lockfiles, Meldung neuer Config-Schlüssel, Gesundheitscheck; Spec 005) | packages/engine/src/spec_agent_kit/install |
| Agent-Skill `sak-init` | implementiert (geführte Einrichtung im Kit-Repo, die Logik steckt im CLI) | .claude/skills/sak-init |
| Collector / Ingest | implementiert (Collector-Seite, Spec 006: `sak board` mit `--json`/`--text`, lokale Ansicht `sak board serve` auf 127.0.0.1, ausfallsicherer `sak push` mit Cursor, Sperre und losgelöstem Hintergrundstart bei `push: auto`; Golden-File- und Push-Tests gegen einen lokalen Test-Server; die Ingest-Seite ist die Dashboard-API, Spec 007) | packages/engine/src/spec_agent_kit/board, packages/engine/src/spec_agent_kit/push |
| Dashboard-API | implementiert (Hono + SQLite, Admin-Login, authentifizierter Ingest mit Contracts-Validierung, Lese-API, Retention, CLI; API-Vertragstests; Spec 007) | apps/dashboard-api |
| Dashboard-Web | implementiert (React/Vite/Tailwind/shadcn: Portfolio, Projekt-Board, Lauf-Ansicht, Admin, Dark Mode, Deep Links; Playwright-E2E und Screenshot-Smoke; Spec 007) | apps/dashboard-web |
| Deployment (Container) | Dockerfile, Compose-Snippet und Caddy-Beispiel vorhanden, `docker build` noch nicht ausgeführt (kein Docker verfügbar) | deploy/dashboard |
| Tests / CI | teilweise (Tests für Contracts und Engine-Gerüst in TS und Python; CI-Workflow mit Smoke-Test für Init und Upgrade auf Windows und Linux vorhanden, noch nicht auf einem Remote gelaufen) | .github/workflows/ci.yml |

## Dokumente

- [docs/architecture-vision.md](docs/architecture-vision.md)
- [docs/adr/0001-framework-grundsatzentscheidungen.md](docs/adr/0001-framework-grundsatzentscheidungen.md)
- [docs/ui/dashboard-concept.md](docs/ui/dashboard-concept.md)
- [specs/](specs/)

## Zielbilder der Dashboard-UI

Die Dashboard-UI kombiniert drei Vollbild-Ebenen:

- `#/portfolio` – Multi-Projekt-Sicht
- `#/project/:projectKey` – Projektansicht mit Stages/Kanban
- `#/run/:projectKey/:runId` – fokussierte Run-/Spec-Ansicht für Multi-Agent-Verläufe

Damit können Links direkt in Tabs bzw. Views springen, zum Beispiel:

- `#/portfolio`
- `#/project/immo-agent`
- `#/project/immo-agent?tab=conflicts`
- `#/run/immo-agent/093-abc`
