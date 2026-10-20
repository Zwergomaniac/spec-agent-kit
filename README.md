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
- **Rollout in weitere Projekte:** Templates + Init-Skript + Agent-Skill
- **Engine-Laufzeit im Zielprojekt:** Python via uv; Dashboard: TypeScript (Hono, React/Vite, SQLite)

## Status je Baustein

| Baustein | Status | Ort |
| --- | --- | --- |
| Pipeline-Engine (Stationen, Urteile, Gates) | Konzept | — (Quelle: ImmoAgent Spec 093) |
| Rollen-/Agent-Definitionen | Konzept | — |
| Contracts (Event-/Board-Vertrag, Statusvokabular) | Konzept (nur EventEnvelope-Typ + Deep-Link-Helfer vorhanden) | packages/contracts |
| Init-Skript | Mock (kopiert 5 Template-Dateien, ohne Validierung/Überschreibschutz) | scripts/init-project.mjs |
| Upgrade-CLI | Konzept | — |
| Agent-Skill spec-agent-init | Konzept | packages/agent-blueprint/templates/root/.claude/skills |
| Collector / Ingest | Konzept | — |
| Dashboard-API | Mock (feste Beispieldaten, ungeschützter In-Memory-Ingest, kein Server-Start) | apps/dashboard-api |
| Dashboard-Web | Konzept (nur Routen-Konstanten) | apps/dashboard-web |
| Deployment (Container) | Konzept (kein Dockerfile) | deploy/dashboard |
| Tests / CI | fehlt | — |

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
