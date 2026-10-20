# Implementation Plan: Projektkonfiguration

**Branch**: `004-project-config` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

## Summary

Die Konfiguration wird als Contract `config.schema.json` angelegt, nach Constitution I. Dazu kommt das Python-Modul `spec_agent_kit.config` mit den Funktionen load, defaults, effective, check, sowie die CLI-Befehle `sak config check|show`. Die Vorlage und zwei Beispiel-Configs entstehen ebenfalls.

## Technical Context

- **Sprache und Abhängigkeiten:** Python ≥ 3.11 mit `pyyaml` und `jsonschema`. Das Schema liegt in `packages/contracts/schema/`, die Synchronisation läuft über `pnpm contracts:check`.
- **Tests:** pytest mit `tmp_path`-Fixture-Repos (git init).

## Constitution Check

| Prinzip | Erfüllt durch |
|---|---|
| I | Die Config ist ein Contract (Schema mit Enum-Abgleich `role` aus dem Vokabular). |
| III | `config check` schreibt nichts. Die Config gehört dem Projekt. |
| IV | Der Kern-Schutz ist hart verdrahtet. Secrets liegen nicht in der Config. |
| VIII | Alle Projektwerte stehen in der Config. Der grep-Test gehört zu Spec 003, Vorlagen. |

## Project Structure

```text
packages/contracts/schema/config.schema.json     # sak.config/1; additionalProperties:false überall; roles: propertyNames = vocabulary.role
packages/contracts/examples/valid/config-*.yml?  # Beispiele als JSON in examples/ (YAML-Beispiele unter agent-blueprint)
packages/engine/src/spec_agent_kit/config/
  __init__.py      # load_config(root) -> EffectiveConfig ; CORE_PROTECTED ; CORE_CLEAN_IGNORE
  defaults.py      # Default-Werte (FR-002)
  check.py         # check(root) -> {ok, errors, warnings}; Frontmatter-Parser (YAML zwischen ---)
packages/engine/src/spec_agent_kit/cli.py         # + config check|show ; gemeinsamer find_root() (sucht .spec-agent/ aufwärts, sonst git toplevel)
packages/engine/tests/test_config.py
packages/agent-blueprint/templates/config/config.yml               # kommentiert, Platzhalter __PROJECT_KEY__, __PROJECT_NAME__, __BASE_BRANCH__
packages/agent-blueprint/templates/config/examples/immoagent.config.yml
packages/agent-blueprint/templates/config/examples/ai-forge.config.yml
```

## Details

- **Mischregeln für Defaults:** Dictionaries werden tief gemischt. Listen ersetzen den Default, außer bei `guard.protected_paths`: Dort wird immer `CORE_PROTECTED` vorangestellt.
- **`dashboard.push`-Default:** `auto`, wenn `url` gesetzt ist, sonst `manual`.
- **Fehlerausgabe:** pro Fehler `{path: "pipeline.roles.code_review.model", message}`. Bei unbekannten Schlüsseln zusätzlich ein Vorschlag (difflib, close match).
- **Werte für `immoagent.config.yml`:** aus `D:\Dev Department\Project Repos\ImmoAgent\.specify\pipeline.yml`.
  - Interpreter-Pfade werden auf `uv run` umgestellt.
  - Die Prüfregeln (owner_id, Layer-Isolation, Conservative Scraping) kommen aus `ImmoAgent/.claude/agents/pipeline-code-reviewer.md` und werden in `review.rules` überführt.
  - Die UI-Pfade und bekannten Regressionstests kommen aus `pipeline-ui-reviewer.md` und werden in den `ui`-Block überführt.
- **`ai-forge.config.yml`:**
  - key `ai-forge`, base_branch `main`
  - `test_fast`: `uv run pytest -q {paths}`; `test_full`: `uv run pytest -q`; `lint`: `uv run ruff check .`
  - `ui_review.enabled: false`
  - `deploy.command: null`
  - Kommentar: „im Pilot zu prüfen“

## Complexity Tracking

Keine Verstöße.
