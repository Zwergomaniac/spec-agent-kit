# CLAUDE.md

## Überblick

Dieses Repository ist ein Mixed Repo aus:

- wiederverwendbarem Spec-Agent-Blueprint
- Mehrprojekt-Dashboard

Beide Bereiche sind absichtlich gemeinsam versioniert.

## Architekturregeln

1. `packages/contracts` ist die Source of Truth für Eventformen, Projektregistrierung und Statusbegriffe.
2. Dashboard-UI muss Deep Links unterstützen.
3. Default-Startansicht des Dashboards ist Portfolio.
4. Dashboard speichert nur Metadaten.
5. Caddy wird extern betrieben und hier nicht verwaltet.

## Arbeitsweise

- Specs entstehen mit spec-kit unter `specs/NNN-*` (Dogfooding).
- Die Hauptsitzung plant (Specs, Pläne, ADRs); Umsetzung erfolgt durch Subagents.
- Umsetzung erst nach ausdrücklichem „umsetzen“ des Betreibers je Spec.
- Referenzimplementierung: `D:\Dev Department\Project Repos\ImmoAgent` (nur lesen). Pilotprojekt: `AI-Forge`.
- Kein `bypassPermissions` als Default in Templates.

## Befehle

Aus dem Wurzelverzeichnis (Node 22+, pnpm 10, Python 3.11+, uv):

```sh
pnpm install
uv sync --project packages/engine

pnpm test                  # vitest aller TS-Pakete + pytest der Engine (pytest dauert etwa 5 Minuten)
pnpm lint                  # tsc je Paket + ruff check packages/engine
pnpm build                 # Contracts, Dashboard-API (esbuild-Bundle), Dashboard-Web

uv run --project packages/engine pytest    # nur Python: die ganze Suite in einem Lauf (nicht in Teilen)
pnpm --filter @sak/dashboard-web e2e       # Playwright-E2E, vorher `pnpm build`; läuft nicht in der CI

pnpm contracts:gen         # Zod-Typen + Python-Schema-Kopie erzeugen
pnpm contracts:check       # gen + Diff-Prüfung; Ergebnis von gen wird eingecheckt

uv run --project packages/engine sak --help    # CLI im Kit-Repo
```

## Wichtige Pfade

- `packages/contracts/schema/` – Quelle (Schemas, `vocabulary.json`, `labels/de.json`, `limits.json`). Nie von Hand: `packages/contracts/src/generated/` und `packages/engine/src/spec_agent_kit/schemas/`.
- `packages/engine/src/spec_agent_kit/` – Engine: `pipeline/`, `config/`, `board/`, `push/`, `install/`, `cli.py`.
- `packages/agent-blueprint/templates/` – Vorlagen für Zielprojekte (projektneutral, nur über `sak init`/`sak upgrade` installiert).
- `apps/dashboard-api/`, `apps/dashboard-web/` – Dashboard; `deploy/dashboard/` – Container-Dateien.
- `.claude/skills/sak-init/` – Init-Skill des Kit-Repos (keine Vorlage).
- `docs/architecture.md` (Architektur, Abweichungen vom Plan), `docs/follow-ups.md` (offene Punkte), `.specify/memory/constitution.md` (hat Vorrang).
- `specs/NNN-*/` – Specs 001 bis 007 umgesetzt, 008 (Pilot) offen.

