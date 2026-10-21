# Tasks: Robustheit aus dem ImmoAgent-Trial

**Input**: [spec.md](spec.md) (US1–US8, B12–B15, Clarifications). Umsetzung als **Strang C** nach dem Merge von Spec 010 Strang 0 und A, Branch `011-hardening`. Die Agents haken nicht ab, das macht der Planer.

- [X] T000 US1 Hooks über den Starter, doctor-Hook-Probe (Hotfix 0.1.1, Merge 15e74c2).
- [ ] T001 [US2/B14] Prompts des UI-Prüfers und des Code-Prüfers (Ausgaben umlenken, keine Links, quotierte Pfade); `sak run cleanup`; Aufruf in `abort`/`combine`; Vorschlag für `clean_ignore` im `init`. Tests: Junction bzw. Symlink unter `runs/<id>/` wird entfernt, das Ziel bleibt (Windows-Junction und POSIX-Symlink).
- [ ] T002 [US3] Worktree-Erkennung, Erben von URL und Schlüssel aus dem Haupt-Checkout, `preflight`-Warnung bei abweichendem `CLAUDE_PROJECT_DIR`. Tests mit echtem `git worktree add` in tmp.
- [ ] T003 [US4] `pyproject`-Analyse im `init`; `doctor --probe-commands`. Tests mit Fixture-pyprojects (Extras, Groups).
- [ ] T004 [US5] Ergänzung im Code-Prüfer-Prompt; `docs/evals/indirect-escalation.md`.
- [ ] T005 [US6] Format-Option, bypass-Erkennung (Bugfix), `status`/403, Plan-Details, Lock-Erklärung. Tests.
- [ ] T006 [B12] Suche nach `sh` in der doctor-Probe an Git-Orten. [B13] `settings_allow` im Lock und Ersetzen beim Upgrade. [B15] `dashboard` erst bei vorhandenem Schlüssel ok. Tests.
- [ ] T007 [US7] `commands.prepare` in den Prompts von Builder und Prüfern und in `doctor --probe-commands`.
- [ ] T008 [US8] `sak hook session-start` und `SessionStart`-Eintrag (Matcher `compact`) im Fragment und im Settings-Merge. Tests (Ausgabe nur bei aktivem Lauf und `source=compact`; gültiges JSON).
- [ ] T009 Kit-Version 0.2.0, alles grün, README und Follow-ups (erledigte Punkte streichen).
