# Tasks: Contracts v1 (inkl. Umsetzung von Spec 001)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [../001-domain-model-vocabulary/spec.md](../001-domain-model-vocabulary/spec.md), [../../docs/architecture.md](../../docs/architecture.md)

## Phase 1: Setup

- [X] T001 Root-Tooling:
  - `package.json` mit Skripten `lint`, `test`, `build`, `contracts:gen`, `contracts:check` (alle echt, kein `echo`)
  - `pnpm-workspace.yaml` (packages/contracts, apps/*)
  - `tsconfig.base.json`
  - `.editorconfig`
  - `.gitattributes` (`* text=auto eol=lf`)
  - Anmerkung: Lesart: `pnpm-workspace.yaml` listet `packages/contracts` und `apps/*` (plan.md), nicht `packages/*`; engine ist ein uv-Projekt, agent-blueprint kein npm-Paket.
  - Anmerkung: Zusatz: `lint` und `test` im Root rufen auch ruff bzw. pytest über uv auf. Wegen `uv run --project packages/engine ruff check` aus dem Wurzelverzeichnis liegt eine Wurzel-`ruff.toml`, die `.specify` und `.claude` (spec-kit-Upstream) ausnimmt.
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
  - Anmerkung: Lesart: Spec 002 nutzt weitere Aufzählungen, die Spec 001 nicht als Ebene führt. Sie wurden als zusätzliche Ebenen aufgenommen, damit jedes Enum im Vokabular steht (Constitution I): `diag_event_type` (`diag.hook`, FR-004), `board_source` (`live`/`snapshot`, FR-006), `hook_phase` (`start`/`stop`, FR-005).
  - Anmerkung: Widerspruch: Spec 001 SC-002 (kein Wert in zwei Ebenen) kollidiert mit Spec 002 FR-006, wo `marker_kind` und `ticker_kind` `deploy`/`verified` teilen (und `verified` auch Station ist). Lesart: die beiden Listen-Ebenen sind von der Eindeutigkeitsprüfung ausgenommen; der Test dokumentiert das.
  - Anmerkung: `run_kind` enthält auch `manual` (reserviert, Spec 001 FR-025).
  - Anmerkung: Zusatz: `schema/limits.json` als gemeinsame Quelle der Größenlimits für TS und Python (statt zweier Konstanten).
- [X] T006 [US1] `packages/contracts/schema/labels/de.json` vollständig.
  - Anmerkung: Labels ohne Vorgabe in Spec 001 wurden nach dem Muster der Tabellen formuliert: Gate-Arten, Ereignisarten, `run_source`, `marker_kind`, `ticker_kind`, `board_source`, `hook_phase`, `diag.hook`. Der Betreiber sollte sie gegenlesen.

## Phase 3: US1–US3 – Schemas

- [X] T007 [US1] `common.schema.json` mit den `$defs` aus plan.md.
- [X] T008 [US2] `event.schema.json` gemäß Spec 002 FR-004 und FR-005.
  - Anmerkung: Entscheidung: Top-Level `anyOf` statt `oneOf`/`if-then`; die Zweige schließen sich über `type` aus, und `json-schema-to-zod` erzeugt daraus eine typisierte Union (bei `oneOf` wäre der Typ `any`).
  - Anmerkung: Lesart: `verdict.recorded` mit `changes_requested` verlangt `must_count >= 1` (Spec 001 FR-018). Längenlimits ohne Vorgabe: Namen/Agent/Modell/Branch 1 bis 100, Titel 1 bis 200, Notizen 300 Zeichen.
  - Anmerkung: `run.escalated.round` ist Pflicht (Spec 002 FR-005 listet `round, gate?, reason`).
- [X] T009 [US3] `board.schema.json` gemäß FR-006.
  - Anmerkung: Lesart: `specs[].descoped = true` erzwingt `stage = null` (Spec 001 FR-007). Marker führen Spec-Nummern als Zahlen, `ticker[].spec` und `attention[].spec` als `NNN-slug`.
- [X] T010 [US2] `ingest.schema.json` gemäß FR-007 (Anfrage und Ergebnis als zwei `$defs` plus Top-Level `oneOf`, oder zwei Dateien; Entscheidung im Code kommentieren).
  - Anmerkung: Entscheidung: eine Datei mit `$defs.request` und `$defs.result` und Top-Level `anyOf`. Das Schema beschreibt den streng gültigen Request; ein Empfänger darf Events einzeln prüfen und nur das betroffene Event in `rejected[]` melden.
- [X] T011 [P] `examples/valid/` und `examples/invalid/`: mindestens ein gültiges Beispiel je Event-Typ, das Pilot-Board (FR-010) und eine Ingest-Anfrage. Ungültig: unbekanntes Feld, falscher Enum-Wert, `ts` ohne Zeitzone, `run_id` fehlt bei `run.started`, falscher projectKey, `reason` mit 501 Zeichen, `changes_requested`-Event mit falschem Typ von `must_count`.

## Phase 4: Generierung und Python-Seite

- [X] T012 `scripts/gen-zod.mjs` → `src/generated/`; `src/index.ts` exportiert Zod-Schemas, Typen, `vocabulary`, `labels`, `LIMITS`.
  - Anmerkung: Der Zod-Generator verdoppelt Backslashes in Mustern nicht. Deshalb sind Backslashes in `pattern` verboten (`[0-9]` statt `\d`, `[.]` statt `\.`); `gen-zod.mjs` bricht sonst ab. Plan-Regex `\d` wurde entsprechend zu `[0-9]` umgeschrieben (gleiche Bedeutung).
- [X] T013 `src/deep-links.ts` gemäß FR-009 (build + parse, Validierung).
- [X] T014 `scripts/sync-python.mjs`. `contracts:check` = gen + sync + `git diff --exit-code` auf die generierten Pfade.
  - Anmerkung: `contracts:check` ist als `scripts/check.mjs` umgesetzt (plattformneutral): gen + sync + `git diff --exit-code` auf `src/generated` und `schemas/`, zusätzlich Meldung unversionierter generierter Dateien.
- [X] T015 `packages/engine/src/spec_agent_kit/contracts.py` gemäß plan.md, inklusive `LIMITS` und `new_ulid()`.
  - Anmerkung: Lesart: `validate_*` geben eine Liste von Fehlermeldungen zurück (leer = gültig) und prüfen auch das Größenlimit. `pattern` wird mit `re.fullmatch` ausgewertet, damit ein Newline am Ende (`$`) wie in JavaScript abgelehnt wird; `date-time` prüft `datetime.fromisoformat` (ohne Zusatzabhängigkeit).

## Phase 5: Tests

- [X] T016 [P] `packages/contracts/test/schemas.test.ts`: ajv gegen die Beispiele, Abgleich Enum ↔ Vokabular, Labels vollständig.
- [X] T017 [P] `packages/contracts/test/zod.test.ts`: Zod beurteilt die Beispiele wie ajv.
- [X] T018 [P] `packages/contracts/test/deep-links.test.ts`.
- [X] T019 [P] `packages/engine/tests/test_contracts.py`: Beispiele, Byte-Gleichheit der Kopie, ULID-Format, Größenlimits.

## Phase 6: Aufräumen

- [X] T020 Entfernen:
  - `examples/event-payloads/`
  - `apps/dashboard-web/src/lib/routes.ts`
  - altes `EventEnvelope`

  `packages/contracts/AGENTS.md` aktualisieren: Quelle ist `schema/`, `generated/` nie von Hand ändern.
- [X] T021 Alles grün: `pnpm install`, `pnpm -r test`, `pnpm contracts:check`, `uv run --project packages/engine pytest`, `uv run --project packages/engine ruff check`. README-Statusmatrix: Contracts → implementiert.
