# AGENTS.md

## Repo-Typ

Mixed Repo mit zwei Produkten in einem gemeinsamen System:

- Spec Agent Kit: Contracts, Engine (`sak`), Blueprint-Vorlagen, Init/Upgrade
- Dashboard: API (`apps/dashboard-api`) und Web (`apps/dashboard-web`)

Befehle und Pfade: `CLAUDE.md`. Architektur: `docs/architecture.md`. Die Constitution (`.specify/memory/constitution.md`) hat Vorrang.

## Wichtige Invarianten

- `packages/contracts` ist führend. Ein neuer Wert steht zuerst im Vokabular und im Schema, erst danach in Engine, Collector oder Dashboard.
- Generierte Dateien nie von Hand ändern: `packages/contracts/src/generated/` und `packages/engine/src/spec_agent_kit/schemas/`. Erzeugen mit `pnpm contracts:gen`, prüfen mit `pnpm contracts:check`.
- Keine Projektwerte im Kern: Engine (`packages/engine/src`) und Vorlagen (`packages/agent-blueprint/templates/claude`, Config-Vorlage) enthalten keine Projektnamen, Pfade, Stack-Befehle oder Interpreter-Pfade. Alles Projektspezifische steht in `.spec-agent/config.yml`. Ein Grep-Test erzwingt das (`packages/engine/tests/pipeline/test_no_project_hardcodes.py`); die Beispiel-Configs unter `templates/config/examples/` sind ausgenommen.
- Nur Metadaten gelangen ins Dashboard: kein Code, keine Diffs, keine Prompts, keine Secrets.
- Das Kit überschreibt im Zielprojekt nie still (Plan vor Apply, `.sak-new` bei Konflikten). Templates setzen nie `bypassPermissions`.
- Das Dashboard ist per URL direkt auf `portfolio`, `project` (mit Tab) und `run` navigierbar. Portfolio ist die Startansicht.
- Caddy wird extern betrieben und hier nicht verwaltet.
- Die Doku behauptet nichts, was nicht existiert (Constitution VII). Die Statusmatrix im README wird mit jeder Spec aktualisiert.

## Arbeitsweise

- Specs unter `specs/NNN-*`, Kette specify, clarify, plan, tasks, implement, analyze. Umsetzung erst nach ausdrücklichem „umsetzen“ des Betreibers je Spec.
- Kein Push und kein Deploy ohne Freigabe des Betreibers.
