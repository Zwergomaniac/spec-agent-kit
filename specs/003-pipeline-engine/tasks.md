# Tasks: Pipeline-Engine

**Input**: [spec.md](spec.md), [plan.md](plan.md), Specs 001, 002, 004, [../../docs/architecture.md](../../docs/architecture.md). Die Referenz `D:\Dev Department\Project Repos\ImmoAgent` wird nur gelesen.

## Phase 1: Grundlagen

- [ ] T001 `pipeline/git.py` und `pipeline/runs.py` (Lauf-ID nach Spec 001 FR-009, resolve_run nach FR-002, idle/stale).
- [ ] T002 `pipeline/events.py`: v1-Hülle, Validierung, Anhängen mit flush.
- [ ] T003 `pipeline/states.py`: Übergangstabelle, Mapping Übergang → Event-Typ(en).
- [ ] T004 Test-Fixture `tests/pipeline/conftest.py` (Fixture-Repo inklusive Config und Agents).

## Phase 2: US1/US2 – Kernablauf

- [ ] T005 `preflight`: sauberer Stand, Sperre, Verwaist-Erkennung, Branch, `run.started` und `round.started`.
- [ ] T006 `state`, `release`, `return`, `abort`.
- [ ] T007 `guard`, `snapshot`, `reviewer-check`.
- [ ] T008 `pipeline/verdict.py` und `verdict`, en und de.
- [ ] T009 `combine`: aktive Rollen, Rundenlimit, Muss-Befunde ausgeben.
- [ ] T010 `merge`: `--no-ff`, bei Konflikt abbrechen und eskalieren, kein Push.
- [ ] T011 `list`, `show`, `event emit`. CLI-Verdrahtung in `cli.py`.

## Phase 3: US3/US4 – Pause, Übernahme, Nur-Prüfung

- [ ] T012 `pause` und `resume`: `paused_from`, Branch-Wechsel bei sauberem Stand, Sperrprüfung.
- [ ] T013 `--takeover` in preflight (`run.taken_over` und `aborted`).
- [ ] T014 `--review-only --base-commit` und Abschluss als `reviewed` in `combine`.

## Phase 4: US5 – Hooks

- [ ] T015 `pipeline/hooks.py` und `sak hook subagent-start|subagent-stop`: Rollen-Mapping über die Config, open-stations, Dauer, einmaliges `diag.hook`, immer Exit 0, keine Ausnahme nach außen.

## Phase 5: Tests

- [ ] T016 Die 40 Fälle aus `ImmoAgent/tests/unit/specify/test_pipeline.py` portieren und auf das neue Modell abbilden. In einer Tabelle im Test-Modul-Docstring steht, welcher alte Test welchem neuen entspricht und welche entfallen, mit Grund.
- [ ] T017 [P] Neue Tests für pause, resume, takeover, review-only, merge (inklusive Konflikt), Hooks und Locale-Urteile.
- [ ] T018 [P] `test_e2e_pilot.py`: 066 (2 Runden → merged), 084 (needs_human → escalated → pause), 088 (Unterbrechung → pause → resume → merged).
- [ ] T019 [P] `test_no_project_hardcodes.py`: grep über Engine und Vorlagen nach `immoagent`, `owner_id`, `graphify`, `.venv/Scripts`, `PYTHONIOENCODING`, `bypassPermissions`.

## Phase 6: Vorlagen

- [ ] T020 `templates/claude/agents/sak-builder.md`, `sak-code-reviewer.md`, `sak-ui-reviewer.md` nach den Generalisierungsregeln in plan.md.
- [ ] T021 [P] `sak-security-reviewer.md` und `sak-docs.md`.
- [ ] T022 `templates/claude/skills/sak-pipeline/SKILL.md` (Orchestrator, Spec FR-014), inklusive Ablaufschritten mit konkreten `sak`-Befehlen, Pause bei Unterbrechung, Deploy-Regel und Commit-Markern.
- [ ] T023 `templates/claude/settings.fragment.json` (Spec FR-015).

## Phase 7: Abschluss

- [ ] T024 Alles grün. README-Statusmatrix: Pipeline-Engine und Rollen-Definitionen → implementiert (Vorlagen; Installation folgt mit Spec 005).
