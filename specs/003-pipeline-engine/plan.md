# Implementation Plan: Pipeline-Engine

**Branch**: `003-pipeline-engine` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

## Summary

`ImmoAgent/.specify/scripts/python/pipeline.py` wird portiert und generalisiert. Ziel ist das Paket `spec_agent_kit.pipeline` mit CLI-Gruppen `sak run`, `sak hook` und `sak event`. Die 40 Referenztests werden mitportiert. Die Agent- und Skill-Vorlagen werden aus den ImmoAgent-Dateien generalisiert.

## Technical Context

- **Sprache und Abhängigkeiten:** Python ≥ 3.11, `pyyaml`, `jsonschema`. Spec 002 liefert `contracts.py`, Spec 004 liefert `config`.
- **Speicher:** Dateien unter `.spec-agent/state/`.
- **Tests:** pytest. Fixture-Repo per `git init` in `tmp_path`, mit `.spec-agent/config.yml`, `.claude/agents/sak-*.md` und `specs/001-x/tasks.md`.
- **Plattform:** Windows und Linux in CI. Git läuft über `subprocess.run([...], text=True, encoding="utf-8")`.

## Constitution Check

| Prinzip | Erfüllt durch |
|---|---|
| I | Events nur über `contracts.validate_event` vor dem Schreiben. Ungültig führt zu einem Fehler in den Tests, im Betrieb zu einem Hinweis und keinem Event. |
| II | Events enthalten nur Felder aus Spec 002. Befund-Texte bleiben in `verdict-*.md` lokal. |
| III | Die Engine schreibt nur unter `.spec-agent/state/`, auf dem Run-Branch und beim Merge. |
| IV | guard und reviewer-check sind mechanisch. Merge ohne Push. Settings-Fragment ohne bypassPermissions. |
| VI | Portierung mit Abweichungstabelle (unten). |
| VII | Die Referenztests werden portiert, dazu E2E-Fixture-Tests. |
| VIII | Rollenliste aus der Config. Keine Projektwerte, grep-Test. |

## Project Structure

```text
packages/engine/src/spec_agent_kit/pipeline/
  __init__.py
  git.py          # git(root,*args), current_branch, is_ancestor, changed_since, dirty_files (mit clean_ignore)
  runs.py         # new_run_id(spec, now), read/write run.json, all_runs, active_run, paused_runs, resolve_run(token), is_stale/idle
  events.py       # emit(root, type, run=None, **data) -> baut v1-Hülle (ULID, ts, project, origin.branch), validiert, hängt an
  states.py       # TRANSITIONS (Spec 001 FR-011), transition(run, new, reason, gate) -> Event-Typ(en)
  verdict.py      # parse_verdict(text, locale) ; Regex für en + de ; Regeln FR-009
  commands.py     # cmd_preflight, cmd_state, cmd_pause, cmd_resume, cmd_release, cmd_return, cmd_abort, cmd_guard, cmd_snapshot, cmd_reviewer_check, cmd_verdict, cmd_combine, cmd_merge, cmd_list, cmd_show, cmd_event_emit
  hooks.py        # cmd_hook(phase, stdin) – nie Exception nach außen, Exit 0
packages/engine/src/spec_agent_kit/cli.py   # Subparser run/hook/event
packages/engine/tests/pipeline/
  conftest.py     # fixture_repo
  test_states.py test_preflight.py test_guard_snapshot.py test_verdict.py test_combine.py test_hooks.py test_pause_resume_takeover.py test_review_only.py test_merge.py test_e2e_pilot.py test_no_project_hardcodes.py
packages/agent-blueprint/templates/claude/
  agents/sak-builder.md sak-code-reviewer.md sak-ui-reviewer.md sak-security-reviewer.md sak-docs.md
  skills/sak-pipeline/SKILL.md
  settings.fragment.json
```

## Abweichungen von der Referenz

| Referenz (`pipeline.py`) | Neu | Grund |
|---|---|---|
| `runs/<spec>/` | `runs/<run_id>/` | Spec 001 FR-009 |
| `STATIONS = ("code","ui")` | aktive Prüfrollen aus der Config | Spec 004 |
| `TERMINAL_STATES = {merged, aborted}` | `{merged, aborted, reviewed}`; `paused` ist ruhend | Spec 001 |
| Urteilszeile nur Deutsch | `Verdict:` (en) und, bei de, `Urteil:` | ADR E4 |
| Event flach | v1-Hülle | Spec 002 |
| Merge im Skill | `sak run merge` | Determinismus, testbar |
| `SPECIFY_INIT_DIR`, `.venv/Scripts/python.exe`, `PYTHONIOENCODING` | `find_root()`, `uv run`, reconfigure | Constitution VIII |
| `config-check` gegen `pipeline.yml` | `sak config check` (Spec 004) | |
| Graphify-Regel in den Prompts | entfällt (Plugin) | ADR E6 |

## Vorlagen: Generalisierungsregeln

- **Quellen:** `ImmoAgent/.claude/agents/pipeline-{builder,code-reviewer,ui-reviewer}.md` und `ImmoAgent/.claude/skills/speckit-pipeline/SKILL.md`. Die Prüfaspekte bleiben inhaltlich gleich: Spec-Treue, Tests, Sicherheit, Migrationen und geschützte Pfade für den Code-Prüfer; Überlauf, Breite, Tap-Ziele, Konsole und Screenshots für den UI-Prüfer. Das Pflicht-Berichtsformat bleibt ebenfalls.
- **Ersetzt werden:**
  - projektspezifische Pfade, Befehle und Regeln → „siehe `sak config show`: `commands.*`, `ui.*`, `review.rules`, `escalation.topics`“
  - `pipeline.py <cmd>` → `uv run --project .spec-agent/engine sak run <cmd>`
  - `Urteil:` → `Verdict:` (mit DE-Hinweis)
  - `[Muss]`/`[Kann]` → `[must]`/`[may]`
- **Neu:** `sak-security-reviewer` (Fokus Secrets, Auth, Injection, Abhängigkeiten) und `sak-docs` (Doku-Abgleich zur Spec, nur Doku-Dateien). Beide sind Vorlagen und standardmäßig inaktiv.
- **Frontmatter:** `name`, `description`, `model`, `effort`. Prüfer bekommen `tools: Read, Grep, Glob, Bash`, der Builder hat keine `tools`-Zeile.
- **Sprache:** Deutsch.

## Complexity Tracking

Keine Verstöße.
