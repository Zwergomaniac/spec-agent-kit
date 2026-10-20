# Tasks: Collector, lokales Board und Push

**Input**: [spec.md](spec.md), [plan.md](plan.md), Specs 001–004. Die Referenz `ImmoAgent/.specify/scripts/python/dev_board.py` und `ImmoAgent/.specify/dev-board/index.html` wird nur gelesen.

## Phase 1: Fixture

- [ ] T001 `tests/fixtures/board_repo/` mit einem Generator für ein deterministisches Fixture-Repo nach Spec US1 (Independent Test).

## Phase 2: US1 – Board-Ableitung

- [ ] T002 `board/git_history.py` (Port).
- [ ] T003 `board/specs.py` (FR-001, FR-002, FR-003 Spec-Teil).
- [ ] T004 `board/runs_view.py` (FR-004, `escalation`- und `stale_run`-Einträge).
- [ ] T005 `board/build.py` (FR-005 bis FR-007; `notes` bei Fehlern, nie abstürzen).
- [ ] T006 CLI `sak board [--json|--text]`, `board/text.py`.
- [ ] T007 Golden-File-Test und Einzeltests (Marker vor dem Task-Commit, unlesbare Datei, abgeschaltete Stationen, descoped, Betreiber-Task, Klärung im Code-Span ignoriert).

## Phase 3: US2 – Lokale Ansicht

- [ ] T008 `board/serve.py` und `static/board.html` (Port der Referenz-HTML auf `sak.board/1`, Labels de eingebettet aus `labels/de.json`). Tests für Host-Prüfung, 404 und 405.

## Phase 4: US3 – Push

- [ ] T009 `push/outbox.py` (Cursor, Reset, kaputte Zeilen).
- [ ] T010 `push/client.py` und `push/run.py` (FR-009, FR-012, Abgelehnt-Protokoll).
- [ ] T011 `spawn_background` und Sperrdatei (FR-010). Auslöser in Hooks und Run-Befehlen (FR-011).
- [ ] T012 CLI `sak push`.
- [ ] T013 Push-Tests (SC-002, SC-003) mit einem lokalen Test-Server.

## Phase 5: Abschluss

- [ ] T014 Optionaler Test `SAK_IMMOAGENT_SPECS=<pfad>` (SC-001). Alles grün. README-Statusmatrix: Collector/Ingest → implementiert (Collector-Seite).
