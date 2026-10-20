# Implementation Plan: Init- und Upgrade-CLI

**Branch**: `005-init-upgrade` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

## Technical Context

- **Sprache:** Python ≥ 3.11, Paket `spec_agent_kit.install`. Abhängigkeiten aus den Specs 002 bis 004 und 006. Templates liegen unter `packages/agent-blueprint/templates/`.
- **Kit-Wurzel finden:** Die Engine kennt ihr Kit-Repo über den Pfad des Pakets (`packages/engine/src/spec_agent_kit` → drei Ebenen hoch). Sie prüft, dass `packages/agent-blueprint/templates` dort existiert. In der vendorten Kopie im Ziel gibt es kein Kit-Repo. Dort sind `init` und `upgrade` deshalb deaktiviert („aus dem Kit-Repo aufrufen“), `doctor` funktioniert.
- **Tests:** pytest. Fixture-Ziel-Repo mit spec-kit-Attrappe (`.specify/init-options.json` Version 0.12.16), eigenem Agent `code-executor.md` und eigenem Hook `SessionStart`.

## Constitution Check

| Prinzip | Erfüllt durch |
|---|---|
| III | Plan vor Apply, Lock-Hashes, `.sak-new` statt Überschreiben, Config nie angefasst, kein Commit |
| IV | Fragment ohne bypassPermissions; Deny-Regeln; Warnung bei bypass im Ziel |
| VII | Smoke-Test in der CI-Matrix |
| VIII | plattformneutrale Pfade, Kopie per `shutil` mit Ignore-Muster |

## Project Structure

```text
packages/engine/src/spec_agent_kit/install/
  __init__.py
  kit.py          # kit_root(), kit_version(), managed_files() -> {zielpfad: quellpfad}
  plan.py         # Action-Dataclass; build_init_plan(...), build_upgrade_plan(...)
  apply.py        # apply(plan) ; schreibt Lock zuletzt
  settings.py     # merge_settings(existing: dict|None, fragment: dict, extra_allow: list[str]) -> (dict, warnings)
  lock.py         # read/write/validate lock (Schema)
  speckit.py      # Version erkennen, Mindestversion
  doctor.py
packages/contracts/schema/lock.schema.json
packages/engine/src/spec_agent_kit/cli.py   # init | upgrade | doctor
packages/engine/tests/install/
.claude/skills/sak-init/SKILL.md             # im Kit-Repo (Bedienoberfläche)
packages/agent-blueprint/AGENTS.md           # neu: Struktur der Templates, Regeln
```

**Zuordnung der verwalteten Dateien:**
- `templates/claude/agents/*` → `.claude/agents/`
- `templates/claude/skills/*` → `.claude/skills/`
- `packages/engine/**` (ohne tests, .venv, `__pycache__`, `.ruff_cache`, `.pytest_cache`) → `.spec-agent/engine/`
- `templates/spec-agent/gitignore` → `.spec-agent/.gitignore`

`config.yml` wird nur angelegt („seed“), nie verwaltet.

## Complexity Tracking

Keine Verstöße.
