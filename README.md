# spec-agent-kit

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
