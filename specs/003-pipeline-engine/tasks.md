# Tasks: Pipeline-Engine

**Input**: [spec.md](spec.md), [plan.md](plan.md), Specs 001, 002, 004, [../../docs/architecture.md](../../docs/architecture.md). Die Referenz `D:\Dev Department\Project Repos\ImmoAgent` wird nur gelesen.

## Phase 1: Grundlagen

- [X] T001 `pipeline/git.py` und `pipeline/runs.py` (Lauf-ID nach Spec 001 FR-009, resolve_run nach FR-002, idle/stale).
  - Anmerkung: Das Paket `spec_agent_kit.pipeline` hat zusätzlich `__init__.py` mit `RefusedError` (Exit 1) und `UsageError` (Exit 2). Die Uhr ist `runs.utcnow()` (in Tests ersetzbar). Lauf-IDs mit Kollisionssuffix `-b`, `-c` bei gleicher Sekunde (erlaubt von `common.schema.json`). Muster für Pfade (`git.matches`): Verzeichnis-Präfix mit `/`, Glob bei `*?[`, sonst exakter Pfad oder Verzeichnis. `resolve_run` nimmt bei Spec-Angabe den jüngsten nicht beendeten Lauf (`paused` zählt als nicht beendet).
- [X] T002 `pipeline/events.py`: v1-Hülle, Validierung, Anhängen mit flush.
  - Anmerkung: `emit(root, type, *, project, run=None, **data)` baut die Hülle (ULID, ts UTC, project, run_id, spec, `origin.branch` = Basis-Branch) und wirft `EventError`, ohne zu schreiben. Die Befehle fangen das ab und melden `warnings: ["Event verworfen: …"]` (Constitution: im Betrieb Hinweis, kein Event); die Test-Hilfe `Repo.sak` lässt solche Hinweise scheitern.
- [X] T003 `pipeline/states.py`: Übergangstabelle, Mapping Übergang → Event-Typ(en).
  - Anmerkung: Ein Wechsel `building → reviewing` hat keinen Ereignistyp im Vokabular und schreibt kein Event (wie in der Referenz). Lesart: `paused → escalated` ist zusätzlich erlaubt, damit ein aus `escalated` pausierter Lauf in den Zustand vor der Pause zurückkehrt (US3); Spec 001 FR-011 nennt nur building und reviewing. `run.taken_over` ersetzt `run.aborted` bei der Übernahme (ein Event, nicht zwei).
- [X] T004 Test-Fixture `tests/pipeline/conftest.py` (Fixture-Repo inklusive Config und Agents).
  - Anmerkung: `Repo`-Hilfsobjekt mit `sak()`, `events()`, `write()`, `commit()`; steuerbare `clock`-Fixture.

## Phase 2: US1/US2 – Kernablauf

- [X] T005 `preflight`: sauberer Stand, Sperre, Verwaist-Erkennung, Branch, `run.started` und `round.started`.
  - Anmerkung: `config check` (Spec 004) ist die Prüfung „Config gültig“; Schemafehler lehnt schon `cli.py` ab (Antwort `{ok:false, errors[]}`). Basis-Branch ist `--base` oder `project.base_branch`; ausgecheckt sein muss der Basis- oder der Spec-Branch (sonst Ablehnung). Weil der Basis-Branch aus der Config kommt, entfällt die Pflicht `--base` auf dem Spec-Branch aus der Referenz. Ein verwaister Lauf wird in Ablehnung und Antwort unter `stale_runs` genannt. Reihenfolge der Prüfungen: Config, Spec, tasks.md, sauberer Stand, Sperre, Branch. Zielbranch aus `branch_pattern`; ein bestehender Branch muss den aktuellen HEAD enthalten (kein Rebase).
- [X] T006 `state`, `release`, `return`, `abort`.
  - Anmerkung: `state` setzt `merged` nie (nur `merge`) und leitet `paused` und die Rückkehr aus `paused` an `pause`/`resume`. `--gate` wird gegen das Vokabular geprüft. `release` und `return` gelten nur für eskalierte Läufe; `return` braucht `--reason` und liegt unterhalb des Rundenlimits.
- [X] T007 `guard`, `snapshot`, `reviewer-check`.
  - Anmerkung: `guard` ändert nichts, meldet aber `gate: protected_paths`; der Orchestrator ruft dann `state … escalated --gate protected_paths`. `reviewer-check` hat laut Spec kein Lauf-Argument: es eskaliert den aktiven Lauf mit Gate `review_integrity` und lehnt ab. Der Snapshot enthält zusätzlich einen Inhalts-Hash jeder geänderten Datei (auch unversionierte), damit Änderungen an unversionierten Dateien auffallen.
- [X] T008 `pipeline/verdict.py` und `verdict`, en und de.
  - Anmerkung: `parse_verdict(text, locale)`: englische Form immer, deutsche Form (`Urteil:`, `[Muss]`, `[Kann]`) nur bei Locale `de` (die Config-Locale ist in v1 immer `de`). `Grund:` und `Reason:` sind in beiden Locales erlaubt. `verdict` verlangt den Zustand `reviewing` und eine aktive Prüfrolle (code_review, ui_review, security_review).
- [X] T009 `combine`: aktive Rollen, Rundenlimit, Muss-Befunde ausgeben.
  - Anmerkung: Fehlt ein Urteil, lehnt `combine` ab (Exit 1, `missing`), statt wie in der Referenz `complete: false` zu melden. `combine` führt den Wechsel aus: `approved`, nächste Runde (`building`), `escalated` mit Gate `round_limit` (letzte Runde) oder `escalated` ohne Gate bei `needs_human`. Das Ergebnis nennt die Muss-Befunde als `[rolle] Text`.
- [X] T010 `merge`: `--no-ff`, bei Konflikt abbrechen und eskalieren, kein Push.
  - Anmerkung: Bei einem Konflikt: `git merge --abort`, zurück auf den Run-Branch, Lauf `escalated` (ohne Gate, Grund „Merge-Konflikt“). Andere Git-Fehler lehnen nur ab und lassen den Lauf `approved`. Ist der Branch schon enthalten, erzeugt Git keinen Merge-Commit; `merge_commit` ist dann der aktuelle HEAD.
- [X] T011 `list`, `show`, `event emit`. CLI-Verdrahtung in `cli.py`.
  - Anmerkung: `event emit` schreibt nur Ereignisse ohne Zustandswechsel (run.escalated, released, returned, paused, aborted, resumed, approved, reviewed, merged, taken_over, round.started); Ereignisse mit eigenem Befehl (run.started, station.*, verdict.recorded, diag.hook) lehnt es ab. `list` zeigt offene Läufe, neueste zuerst. Verdrahtung: `cli.py` und `pipeline/cli_bridge.py` (Parser und Verteilung; Plan nannte nur cli.py).

## Phase 3: US3/US4 – Pause, Übernahme, Nur-Prüfung

- [X] T012 `pause` und `resume`: `paused_from`, Branch-Wechsel bei sauberem Stand, Sperrprüfung.
  - Anmerkung: Lesart: Ein aus `escalated` pausierter Lauf kehrt bei `resume` nach `escalated` zurück (Zustand vor der Pause). `resume` wählt bei Spec-Angabe den jüngsten pausierten Lauf, prüft die Sperre, wechselt den Branch nur bei sauberem Stand und schreibt `run.resumed`.
- [X] T013 `--takeover` in preflight (`run.taken_over` und `aborted`).
  - Anmerkung: Nur ein verwaister aktiver Lauf lässt sich übernehmen; ein frischer wird mit Hinweis abgelehnt. Es entsteht nur `run.taken_over` (kein zusätzliches `run.aborted`). Die Übernahme geschieht erst nach erfolgreichem Branch-Wechsel für den neuen Lauf.
- [X] T014 `--review-only --base-commit` und Abschluss als `reviewed` in `combine`.
  - Anmerkung: Die Spec nennt in US4 `--base <commit>`, in FR-001 `--base-commit <sha>`; umgesetzt ist FR-001. Der Lauf bleibt auf dem ausgecheckten Branch, startet in `reviewing` (Events run.started mit kind `review_only` und round.started), braucht einen sauberen Stand. `combine`: approve → `reviewed`, sonst `escalated` (ohne Gate). Ein solcher Lauf wird nie gemergt.

## Phase 4: US5 – Hooks

- [X] T015 `pipeline/hooks.py` und `sak hook subagent-start|subagent-stop`: Rollen-Mapping über die Config, open-stations, Dauer, einmaliges `diag.hook`, immer Exit 0, keine Ausnahme nach außen.
  - Anmerkung: Der Hook schreibt nichts auf stdout (SubagentStart-Ausgaben könnten als Kontext in den Subagent gelangen). `diag.hook` entsteht je Phase einmal, nur bei fehlendem Agent-Typ und nur bei aktivem Lauf (Spec: „Hook ohne aktiven Lauf: kein Event“). Agent-Typ → Rolle über `pipeline.roles.<rolle>.agent` der aktiven Rollen; ein Stop ohne Start schreibt `duration_s: 0`. Parallel startende Prüfer schützt eine kurze Dateisperre um `open-stations.json` (höchstens 0,5 s). Ungültige Aufrufe von `sak hook …` enden ebenfalls mit Exit 0.

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
