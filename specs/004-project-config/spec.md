# Feature Specification: Projektkonfiguration (Konfigurationsgrenze)

**Feature Branch**: `004-project-config`

**Created**: 2026-10-20

**Status**: Draft

**Input**: ADR 0001 E6–E8, Constitution IV und VIII. ImmoAgent 093 `contracts/pipeline-config.md` (FR-010: „einzige Stelle für Projektspezifisches“).

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Alles Projektspezifische an einer Stelle (Priority: P1)

Der Betreiber passt das Kit an ein Projekt an, ohne Kit-Dateien (Engine, Agents, Skills) zu ändern. Dazu gehören Testbefehle, Rollen, geschützte Pfade, Prüfthemen, Deploy-Befehl und Dashboard-Ziel. Er ändert dafür nur `.spec-agent/config.yml`.

**Independent Test**: Für ImmoAgent und AI-Forge gibt es je eine Config, mit der sich die Pipeline vollständig beschreiben lässt. Agent- und Skill-Dateien sind für beide Projekte identisch.

**Acceptance Scenarios**:

1. **Given** AI-Forge ohne Web-UI, **When** `ui_review.enabled: false` gesetzt ist, **Then** läuft keine UI-Prüfstation, und das Gesamturteil entsteht aus `code_review` allein.
2. **Given** ein Projekt mit pytest über uv, **When** `commands.test_fast` auf `uv run pytest -q {paths}` gesetzt ist, **Then** verwendet der Builder genau diesen Befehl.

### User Story 2 – Fehlkonfiguration fällt vor dem Lauf auf (Priority: P1)

`sak config check` meldet ungültige Werte, fehlende Agent-Dateien und Abweichungen zwischen Config und Agent-Frontmatter (Modell, Effort), bevor ein Lauf startet.

**Acceptance Scenarios**:

1. **Given** in der Config steht `code_review.model: opus`, im Agent-Frontmatter aber `sonnet`, **When** `config check` läuft, **Then** folgt eine Ablehnung mit beiden Werten.
2. **Given** ein unbekannter Schlüssel `pipeline.max_round`, **When** geprüft wird, **Then** folgt eine Ablehnung mit dem Hinweis auf den Tippfehler.

### User Story 3 – Kern-Schutz ist nicht abschaltbar (Priority: P1)

Die Pipeline-Dateien des Kits sind immer geschützt, auch wenn die Projekt-Config sie nicht aufführt.

**Acceptance Scenarios**:

1. **Given** `guard.protected_paths: []`, **When** der Builder `.spec-agent/config.yml` ändert, **Then** eskaliert `guard` trotzdem.

### Edge Cases

- **Config fehlt:** Alle `sak`-Befehle außer `init` und `version` lehnen mit „nicht initialisiert“ ab.
- **Rolle aktiviert, Agent-Datei fehlt:** `config check` lehnt ab.
- **Keine Prüfrolle aktiv:** Das ist ungültig. Mindestens `code_review` muss aktiv sein.
- **`{paths}` fehlt in `test_fast`:** erlaubt. Der Befehl läuft dann ohne Pfadeinschränkung.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Die Projektkonfiguration MUSS in `.spec-agent/config.yml` liegen (YAML), eingecheckt. Ihre Form legt das JSON Schema `packages/contracts/schema/config.schema.json` fest (`schema: sak.config/1`). Die Config ist Teil der Contracts, nach Constitution I. Unbekannte Schlüssel sind unzulässig.
- **FR-002**: Die Config MUSS folgende Bereiche haben. Defaults stehen in Klammern.

  | Bereich | Inhalt |
  |---|---|
  | `project` | `key` (Spec 001 FR-004), `name`, `base_branch` (`main`) |
  | `locale` | `de` |
  | `pipeline` | `max_rounds` (2, 1–5), `idle_minutes` (60), `stale_hours` (6), `branch_pattern` (`{spec}`) |
  | `pipeline.roles` | je Rolle aus dem Vokabular: `enabled`, `agent` (Dateiname ohne `.md`), `model`, `effort`. Defaults: `builder`, `code_review` und `ui_review` aktiv, `security_review` und `docs` inaktiv. `integrator` ist in v1 nicht aktivierbar. |
  | `stages` | `deployed` (true), `verified` (true) — abschaltbare Stationen (Spec 001) |
  | `commands` | `test_fast[]` (mit optionalem `{paths}`), `test_full[]`, `lint[]`, `environment_failures[]` (Textmuster) |
  | `ui` | nur nötig, wenn `ui_review` aktiv ist: `command`, `base_url`, `paths[]` (Frontend-Pfade), `viewports{name:[w,h]}`, `checks[]`, `regression_tests[]` |
  | `guard` | `protected_paths[]` (zusätzlich zum Kern), `clean_ignore[]` |
  | `escalation` | `paths[]` (Hinweise an Prüfer), `topics[]` (fachliche Themen → `needs_human`) |
  | `review` | `rules[]`: projektspezifische Prüfregeln als kurze Sätze, zum Beispiel „Jede Abfrage nach Kontodaten filtert nach owner_id“ |
  | `orchestrator_only` | Liste von Aktionen, die nie ein Subagent ausführt, zum Beispiel `deploy`, `ssh` |
  | `deploy` | `command` (oder null); wird nur vom Orchestrator nach Freigabe ausgeführt |
  | `dashboard` | `url` (oder null), `token_env` (`SAK_DASHBOARD_TOKEN`), `push` (`auto`\|`manual`\|`off`, Default `manual`, solange `url` null ist; sonst `auto`), `share_commit_subjects` (false) |
  | `plugins` | Liste aktivierter Plugin-Namen (in v1 nur reserviert; leer) |

- **FR-003**: Der Kern-Schutz MUSS in der Engine fest verankert sein und gilt immer:
  - `.spec-agent/config.yml`
  - `.spec-agent/engine/`
  - `.spec-agent/lock.json`
  - `.claude/agents/sak-*`
  - `.claude/skills/sak-*`
  - `.claude/settings.json`
  - `.claude/settings.local.json`
  - `.specify/memory/constitution.md`

  `guard.protected_paths` ergänzt diese Liste, ersetzt sie aber nicht. Zusätzlich gilt `.spec-agent/state/` immer als `clean_ignore`.
- **FR-004**: `sak config check` MUSS prüfen:
  - das Schema
  - ob für jede aktive Rolle `.claude/agents/<agent>.md` existiert
  - ob Modell und Effort im Frontmatter übereinstimmen
  - ob mindestens `builder` und `code_review` aktiv sind
  - ob bei aktivem `ui_review` ein `ui`-Block vorhanden ist
  - ob der `base_branch` existiert

  Ausgabe ist JSON (`ok`, `errors[]`, `warnings[]`). Exit 1 bei Fehlern.
- **FR-005**: `sak config show` MUSS die wirksame Config ausgeben, also mit Defaults und dem Kern-Schutz. Agents und Skill lesen projektspezifische Werte nur darüber oder über die Datei. Prompts enthalten keine projektspezifischen Werte.
- **FR-006**: Die Engine MUSS Secrets nie aus der Config lesen. Den Dashboard-Schlüssel liest sie aus der Umgebungsvariable `token_env` oder aus der gitignorierten Datei `.spec-agent/dashboard.key`.
- **FR-007**: Unter `packages/agent-blueprint/templates/config/` MÜSSEN liegen:
  - eine kommentierte Vorlage `config.yml`
  - die Beispiele `examples/immoagent.config.yml` und `examples/ai-forge.config.yml`

  Die ImmoAgent-Werte stammen aus dessen `pipeline.yml`. Die AI-Forge-Werte sind nach bestem Wissen gewählt (Python, uv, pytest, ruff, kein UI) und werden im Pilot überprüft.

### Key Entities

Projektkonfiguration, Rolle (Besetzung), wirksame Konfiguration.

## Success Criteria *(mandatory)*

- **SC-001**: Für jedes projektspezifische Detail aus der Bestandsaufnahme (Testbefehle, Frontend-Pfade, owner_id-Regel, Portal-Drosselung, Deploy-Skript, Migrationspfade) gibt es ein Config-Feld. In Agents, Skills und Engine kommt keines davon vor (grep-Test).
- **SC-002**: `config check` erkennt alle Fehlerfälle aus den Edge Cases und FR-004, abgesichert durch Tests.

## Assumptions

- YAML wird nur als Daten gelesen (`safe_load`) und anschließend gegen das Schema geprüft.
- `effort` nimmt die Werte von Claude Code an (`low`, `medium`, `high`). Die Config erzwingt keine Obergrenze, die Vorlage empfiehlt `medium`.
