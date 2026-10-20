# Feature Specification: Pilot AI-Forge

**Feature Branch**: `008-pilot-ai-forge`

**Created**: 2026-10-20

**Status**: Draft

**Input**: ADR 0001 E11. Pilotprojekt `D:\Dev Department\Project Repos\AI-Forge`:
- Python 3.12, `uv.lock`, VPS
- keine Web-UI
- spec-kit 0.12.16
- eigene Agents `code-executor` und `mendix-studio-pro-agent`, Hook `session-start.sh`
- 24 Specs

## Ziel

Das Kit wird unter realen Bedingungen generalisiert erprobt. Das Ergebnis ist eine Auswertung mit Befunden, aus denen Folge-Specs entstehen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Init ohne Schaden (Priority: P1)

`sak init` mit Plan, Prüfung durch den Betreiber und Apply auf einem eigenen Branch in AI-Forge.

**Acceptance Scenarios**:
1. **Given** AI-Forge mit eigenen Agents und Hooks, **When** der Init angewendet wird, **Then** ist `git diff` auf bestehende Dateien leer, mit Ausnahme des additiven Merges in `settings.json`, und `sak doctor` ist ok.

### User Story 2 – Lokales Board zeigt AI-Forge richtig (Priority: P1)

`sak board --text` und `sak board serve` zeigen die 24 Specs mit plausiblen Stationen. Abweichungen werden als Befund festgehalten, etwa durch andere Artefaktnamen in spec-kit 0.12.

### User Story 3 – Ein echter Pipeline-Lauf (Priority: P1)

Der Betreiber wählt eine kleine, freigegebene AI-Forge-Spec. Der Lauf geht über `/sak-pipeline` mit Builder und Code-Prüfer, ohne UI-Prüfer, bis `merged` oder `escalated`. Events entstehen, und das Board zeigt den Lauf.

### User Story 4 – Push ans Dashboard (Priority: P2)

Sobald ein Dashboard läuft (lokal per `pnpm dev` oder auf dem VPS), wird AI-Forge dort angelegt, und der Push wird geprüft.

## Requirements *(mandatory)*

- **FR-001**: Alle Schritte in AI-Forge passieren auf einem eigenen Branch `sak-pilot`. Es gibt keinen Push und keinen Deploy. Eine bestehende uncommittete Änderung (`scripts/aiforge.ps1`) bleibt unberührt.
- **FR-002**: Jeder Schreibschritt in AI-Forge braucht die ausdrückliche Freigabe des Betreibers in der Sitzung.
- **FR-003**: Die Auswertung `specs/008-pilot-ai-forge/evaluation.md` enthält:
  - Befunde, gegliedert nach Init, Board, Lauf und Push
  - Zeitbedarf
  - Abweichungen zwischen spec-kit-Versionen
  - Empfehlungen als Kandidaten für Folge-Specs

## Success Criteria *(mandatory)*

- **SC-001**: Init, doctor und Board laufen ohne manuelle Korrektur an Kit-Dateien.
- **SC-002**: Ein Lauf endet in einem definierten Zustand (`merged`, `escalated` oder `paused`). Die Event-Folge ist gültig.
- **SC-003**: Die Auswertung liegt vor, und alle Befunde haben eine Empfehlung.

## Assumptions

- Die Auswahl der Pilot-Spec und die Freigabe „umsetzen“ für diese Spec trifft der Betreiber.
