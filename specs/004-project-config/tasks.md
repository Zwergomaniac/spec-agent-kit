# Tasks: Projektkonfiguration

**Input**: [spec.md](spec.md), [plan.md](plan.md), [../../docs/architecture.md](../../docs/architecture.md), Contracts aus Spec 002

## Phase 1: Contract

- [X] T001 `packages/contracts/schema/config.schema.json` gemäß Spec FR-002, sowie das Vokabular für den Rollen-Abgleich. Zusätzlich ein gültiges und mehrere ungültige Beispiele (JSON) unter `packages/contracts/examples/`. `pnpm contracts:gen`; die Tests in TS und Python decken das neue Schema ab.
  - Anmerkung: Der Plan nennt `propertyNames` für die Rollen. Der Zod-Generator bildet `propertyNames` und `allOf` nicht ab (Zod würde unbekannte Rollen und einen aktiven Integrator akzeptieren). Deshalb sind die sechs Rollen unter `pipeline.roles` ausgeschrieben (`additionalProperties: false`, Integrator mit `enabled: const false`), und ein Test erzwingt die Übereinstimmung mit der Vokabular-Ebene `role`. `effort` und `dashboard.push` sind `anyOf` von Konstanten, weil sie nicht zum Vokabular gehören (Enums verlangen `x-vocab`). Beispiele liegen als `config-*.json` unter `examples/valid` und `examples/invalid`.

## Phase 2: US1/US3 – Laden und wirksame Config

- [X] T002 `spec_agent_kit/config/defaults.py` und `__init__.py`: `load_config`, Mischregeln, `CORE_PROTECTED` und `CORE_CLEAN_IGNORE` (Spec FR-003).
  - Anmerkung: Defaults: Rollen heißen laut Tabelle `DEFAULT_AGENTS` (Spec 003 FR-013, zum Beispiel `sak-code-reviewer`); Modelle: builder sonnet, code_review opus, ui_review sonnet, security_review opus, docs sonnet (aus der ImmoAgent-Besetzung abgeleitet), effort `medium`. `orchestrator_only` hat als Default eine leere Liste (die Spec nennt nur Beispiele); die Vorlage trägt `deploy` und `ssh` ein. Neben `load_config` gibt es `read_raw`, `schema_errors`, `build_effective` und `read_dashboard_key` (FR-006).
- [X] T003 `find_root()` in `cli.py`. Fehlende Config → Exit 1 mit „nicht initialisiert“ (außer `version` und, später, `init`).
  - Anmerkung: Ohne Projektwurzel oder ohne Config antworten alle Befehle außer `version` mit JSON `ok: false` und Exit 1. `init` existiert erst mit Spec 005.
- [X] T004 `sak config show`.
  - Anmerkung: Ausgabe ist die wirksame Config als JSON (ohne `ok`-Hülle), bei Fehlern `{ok:false, errors, warnings}` mit Exit 1.

## Phase 3: US2 – Prüfung

- [X] T005 `config/check.py` mit allen Prüfungen aus FR-004 inklusive Frontmatter-Vergleich und Tippfehler-Vorschlag.
  - Anmerkung: Fehlt im Agent-Frontmatter `model` oder `effort`, ist das eine Warnung, kein Fehler (nur echte Abweichungen lehnen ab). Weitere Prüfungen über FR-004 hinaus: `pipeline.branch_pattern` muss `{spec}` enthalten (Fehler), ein `ui`-Block bei inaktivem `ui_review` wird als Warnung gemeldet. Die Prüfungen nach dem Schema laufen nur bei schemagültiger Config. Als vorhanden gilt ein Basis-Branch lokal oder unter `origin/`.
- [X] T006 `sak config check`.
  - Anmerkung: Exit 1 bei Fehlern oder fehlender Config (Ausgabe `{ok:false, errors, warnings}`), sonst 0.

## Phase 4: Vorlagen

- [X] T007 [P] `packages/agent-blueprint/templates/config/config.yml`, kommentiert, in deutscher Sprache.
  - Anmerkung: Platzhalter `__PROJECT_KEY__`, `__PROJECT_NAME__`, `__BASE_BRANCH__`. `ui_review` ist in der Vorlage inaktiv (der `ui`-Block steht auskommentiert), `orchestrator_only` trägt `deploy` und `ssh` ein.
- [X] T008 [P] `examples/immoagent.config.yml`, Quellen laut plan.md.
  - Anmerkung: `ui.backend` aus der ImmoAgent-Quelle hat in `sak.config/1` kein Feld (Spec FR-002 nennt es nicht) und entfällt; `tests.full` ist in `test_full` (Tests) und `lint` aufgeteilt; `protected_paths` führt nur Ergänzungen zum Kern-Schutz.
- [X] T009 [P] `examples/ai-forge.config.yml`.
  - Anmerkung: `stages` bleibt auf den Defaults, obwohl `deploy.command` null ist. Das ist im Pilot zu klären.

## Phase 5: Tests und Abschluss

- [X] T010 `packages/engine/tests/test_config.py`:
  - Defaults
  - Kern-Schutz nicht abschaltbar
  - unbekannter Schlüssel mit Vorschlag
  - Frontmatter-Abweichung
  - fehlende Agent-Datei
  - `ui_review` aktiv ohne `ui`-Block
  - keine Prüfrolle aktiv
  - beide Beispiel-Configs sind gültig
  - Anmerkung: Zusätzlich getestet: Mischregeln, `dashboard.push`-Default, Integrator nicht aktivierbar, `branch_pattern`, Basis-Branch, Secrets-Quellen (FR-006), Vorlage nach Platzhalter-Ersetzung, CLI-Exit-Codes sowie ein grep-Test, dass der Engine-Quelltext keine Projektwerte enthält.
- [X] T011 Alles grün (TS, Python, ruff, `contracts:check`). README-Statusmatrix: Zeile „Projektkonfiguration“ ergänzen.
  - Anmerkung: README-Statusmatrix: neue Zeile "Projektkonfiguration". Lauf: `pnpm -r test` (147 Tests), `pnpm contracts:check`, `pytest -q` (125 Tests), `ruff check` grün.
