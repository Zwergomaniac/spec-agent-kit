# Tasks: Contracts v1 (inkl. Umsetzung von Spec 001)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [../001-domain-model-vocabulary/spec.md](../001-domain-model-vocabulary/spec.md), [../../docs/architecture.md](../../docs/architecture.md)

## Phase 1: Setup

- [X] T001 Root-Tooling:
  - `package.json` mit Skripten `lint`, `test`, `build`, `contracts:gen`, `contracts:check` (alle echt, kein `echo`)
  - `pnpm-workspace.yaml` (packages/contracts, apps/*)
  - `tsconfig.base.json`
  - `.editorconfig`
  - `.gitattributes` (`* text=auto eol=lf`)
- [X] T002 [P] Paket `packages/contracts/package.json` (`@sak/contracts`) mit den Abhängigkeiten aus plan.md; vitest-Konfiguration.
- [X] T003 [P] Python-Projekt `packages/engine`:
  - `pyproject.toml`
  - `src/spec_agent_kit/__init__.py`
  - `cli.py` mit `sak version` und UTF-8-Reconfigure
  - `uv sync`
  - ruff-Konfiguration
- [X] T004 [P] `.github/workflows/ci.yml` für TS und Python (Matrix ubuntu und windows).

## Phase 2: US1 – Vokabular und Labels (Spec 001)

- [X] T005 [US1] `packages/contracts/schema/vocabulary.json` mit allen Ebenen und Werten aus Spec 001: FR-006, FR-010, FR-015, FR-016 (station_state), FR-017, FR-018, FR-020, FR-021, FR-022, FR-025. Dazu `run_source`, `marker_kind`, `ticker_kind`.
- [X] T006 [US1] `packages/contracts/schema/labels/de.json` vollständig.

## Phase 3: US1–US3 – Schemas

- [X] T007 [US1] `common.schema.json` mit den `$defs` aus plan.md.
- [X] T008 [US2] `event.schema.json` gemäß Spec 002 FR-004 und FR-005.
- [X] T009 [US3] `board.schema.json` gemäß FR-006.
- [X] T010 [US2] `ingest.schema.json` gemäß FR-007 (Anfrage und Ergebnis als zwei `$defs` plus Top-Level `oneOf`, oder zwei Dateien; Entscheidung im Code kommentieren).
- [X] T011 [P] `examples/valid/` und `examples/invalid/`: mindestens ein gültiges Beispiel je Event-Typ, das Pilot-Board (FR-010) und eine Ingest-Anfrage. Ungültig: unbekanntes Feld, falscher Enum-Wert, `ts` ohne Zeitzone, `run_id` fehlt bei `run.started`, falscher projectKey, `reason` mit 501 Zeichen, `changes_requested`-Event mit falschem Typ von `must_count`.

## Phase 4: Generierung und Python-Seite

- [X] T012 `scripts/gen-zod.mjs` → `src/generated/`; `src/index.ts` exportiert Zod-Schemas, Typen, `vocabulary`, `labels`, `LIMITS`.
- [X] T013 `src/deep-links.ts` gemäß FR-009 (build + parse, Validierung).
- [X] T014 `scripts/sync-python.mjs`. `contracts:check` = gen + sync + `git diff --exit-code` auf die generierten Pfade.
- [X] T015 `packages/engine/src/spec_agent_kit/contracts.py` gemäß plan.md, inklusive `LIMITS` und `new_ulid()`.

## Phase 5: Tests

- [ ] T016 [P] `packages/contracts/test/schemas.test.ts`: ajv gegen die Beispiele, Abgleich Enum ↔ Vokabular, Labels vollständig.
- [ ] T017 [P] `packages/contracts/test/zod.test.ts`: Zod beurteilt die Beispiele wie ajv.
- [ ] T018 [P] `packages/contracts/test/deep-links.test.ts`.
- [ ] T019 [P] `packages/engine/tests/test_contracts.py`: Beispiele, Byte-Gleichheit der Kopie, ULID-Format, Größenlimits.

## Phase 6: Aufräumen

- [ ] T020 Entfernen:
  - `examples/event-payloads/`
  - `apps/dashboard-web/src/lib/routes.ts`
  - altes `EventEnvelope`

  `packages/contracts/AGENTS.md` aktualisieren: Quelle ist `schema/`, `generated/` nie von Hand ändern.
- [ ] T021 Alles grün: `pnpm install`, `pnpm -r test`, `pnpm contracts:check`, `uv run --project packages/engine pytest`, `uv run --project packages/engine ruff check`. README-Statusmatrix: Contracts → implementiert.
