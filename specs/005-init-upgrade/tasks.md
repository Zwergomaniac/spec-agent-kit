# Tasks: Init- und Upgrade-CLI

**Input**: [spec.md](spec.md), [plan.md](plan.md), Specs 002–004 und 006, [../../docs/architecture.md](../../docs/architecture.md)

## Phase 1: Grundlagen

- [X] T001 `lock.schema.json` mit Beispielen, Generierung und Tests (Contracts-Workflow wie Spec 002).
- [X] T002 `install/kit.py`, `install/lock.py`, `install/speckit.py`.
- [X] T003 `templates/spec-agent/gitignore`.
- [X] T004 Fixture-Ziel-Repo-Generator in `tests/install/conftest.py`.

## Phase 2: US1 – Init

- [X] T005 `install/settings.py` (FR-005) mit Tests: fehlende Datei, bestehende Hooks, bypass-Warnung, Idempotenz, ungültiges JSON.
- [X] T006 `install/plan.py` für init (FR-001 bis FR-003, FR-006), Validierung (FR-002).
- [X] T007 `install/apply.py` und CLI `sak init`. Nach Apply: `uv sync` und `config check` (FR-009).
- [X] T008 Tests für US1 inklusive aller Acceptance Scenarios und SC-002.

## Phase 3: US2 – Upgrade

- [ ] T009 Upgrade-Plan (replace, delete, conflict, skip) und Meldung neuer Config-Schlüssel. CLI `sak upgrade`.
- [ ] T010 Tests für US2 und Idempotenz (SC-001).

## Phase 4: US4 – Doctor

- [ ] T011 `install/doctor.py` und CLI `sak doctor` mit Tests.

## Phase 5: US3 – Skill und Aufräumen

- [ ] T012 `.claude/skills/sak-init/SKILL.md` im Kit-Repo: Fragen, Plan zeigen, nach Bestätigung `--apply`, doctor, nächste Schritte (Commit-Vorschlag, Dashboard-Projekt anlegen, Schlüssel in `.spec-agent/dashboard.key` oder Env).
- [ ] T013 Altes Gerüst entfernen (FR-010). `packages/agent-blueprint/AGENTS.md` neu schreiben.

## Phase 6: Abschluss

- [ ] T014 Smoke-Test SC-003 in CI (Windows und Linux). Alles grün. README-Statusmatrix: Init-Skript → ersetzt durch `sak init` (implementiert), Upgrade-CLI und Agent-Skill → implementiert.
