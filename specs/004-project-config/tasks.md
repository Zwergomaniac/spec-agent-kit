# Tasks: Projektkonfiguration

**Input**: [spec.md](spec.md), [plan.md](plan.md), [../../docs/architecture.md](../../docs/architecture.md), Contracts aus Spec 002

## Phase 1: Contract

- [X] T001 `packages/contracts/schema/config.schema.json` gemäß Spec FR-002, sowie das Vokabular für den Rollen-Abgleich. Zusätzlich ein gültiges und mehrere ungültige Beispiele (JSON) unter `packages/contracts/examples/`. `pnpm contracts:gen`; die Tests in TS und Python decken das neue Schema ab.
  - Anmerkung: Der Plan nennt `propertyNames` für die Rollen. Der Zod-Generator bildet `propertyNames` und `allOf` nicht ab (Zod würde unbekannte Rollen und einen aktiven Integrator akzeptieren). Deshalb sind die sechs Rollen unter `pipeline.roles` ausgeschrieben (`additionalProperties: false`, Integrator mit `enabled: const false`), und ein Test erzwingt die Übereinstimmung mit der Vokabular-Ebene `role`. `effort` und `dashboard.push` sind `anyOf` von Konstanten, weil sie nicht zum Vokabular gehören (Enums verlangen `x-vocab`). Beispiele liegen als `config-*.json` unter `examples/valid` und `examples/invalid`.

## Phase 2: US1/US3 – Laden und wirksame Config

- [X] T002 `spec_agent_kit/config/defaults.py` und `__init__.py`: `load_config`, Mischregeln, `CORE_PROTECTED` und `CORE_CLEAN_IGNORE` (Spec FR-003).
  - Anmerkung: Defaults: Rollen heißen `sak-<rolle mit Bindestrich>` (zum Beispiel `sak-code-review`); Modelle: builder sonnet, code_review opus, ui_review sonnet, security_review opus, docs sonnet (aus der ImmoAgent-Besetzung abgeleitet), effort `medium`. `orchestrator_only` hat als Default eine leere Liste (die Spec nennt nur Beispiele); die Vorlage trägt `deploy` und `ssh` ein. Neben `load_config` gibt es `read_raw`, `schema_errors`, `build_effective` und `read_dashboard_key` (FR-006).
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

- [ ] T007 [P] `packages/agent-blueprint/templates/config/config.yml`, kommentiert, in deutscher Sprache.
- [ ] T008 [P] `examples/immoagent.config.yml`, Quellen laut plan.md.
- [ ] T009 [P] `examples/ai-forge.config.yml`.

## Phase 5: Tests und Abschluss

- [ ] T010 `packages/engine/tests/test_config.py`:
  - Defaults
  - Kern-Schutz nicht abschaltbar
  - unbekannter Schlüssel mit Vorschlag
  - Frontmatter-Abweichung
  - fehlende Agent-Datei
  - `ui_review` aktiv ohne `ui`-Block
  - keine Prüfrolle aktiv
  - beide Beispiel-Configs sind gültig
- [ ] T011 Alles grün (TS, Python, ruff, `contracts:check`). README-Statusmatrix: Zeile „Projektkonfiguration“ ergänzen.
