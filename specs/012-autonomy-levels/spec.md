# Feature Specification: Autonomie-Stufen (Merge, Push, Deploy)

**Feature Branch**: `012-autonomy-levels`

**Created**: 2026-10-21

**Status**: Implemented (Kit 0.3.0)

**Input**: Betreiber 2026-10-21 beim produktiven Einsatz in ImmoAgent: „Darf der Main-Agent nicht mergen, pushen oder deployen? Das gefällt mir gar nicht.“ Die Entscheidungen fielen im Chat am selben Tag.

## Clarifications

### Session 2026-10-21

- Q: Wie autonom ist der Orchestrator nach `approved`? → A: Merge und Push automatisch, als Projekt-Einstellung. Für neue Projekte bleibt der Default streng.
- Q: Deploy? → A: Nur nach ausdrücklichem OK des Betreibers im Chat, dann führt der Orchestrator ihn selbst aus (wie bisher).
- Q: Eskalationen? → A: Bleiben beim Betreiber. Fachliche Themen und Rundenlimit stoppen den Lauf bis `release`.
- Push läuft ausschließlich über `sak run push`. Die Deny-Regel `git push` für direkte Aufrufe bleibt bestehen und schützt weiterhin vor Pushes durch Subagents und vor Force-Push.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Push nach Merge ohne Zutun (Priority: P1)

**Acceptance Scenarios**:
1. **Given** `autonomy.push: after_merge` und ein Lauf in `merged`, **When** der Orchestrator `sak run push <run>` ausführt, **Then** wird der Basis-Branch auf das konfigurierte Remote gepusht (fast-forward, ohne `--force`), und das Event `run.pushed` mit Remote, Branch und Commit wird geschrieben.
2. **Given** das Remote ist weiter als lokal (non-fast-forward), **When** gepusht wird, **Then** wird abgelehnt, ohne Merge und ohne Rebase, und der Lauf bekommt einen Aufmerksamkeitseintrag „Push abgelehnt“.
3. **Given** `autonomy.push: manual` (Default), **When** `sak run push` aufgerufen wird, **Then** wird mit dem Hinweis auf die Config abgelehnt.
4. **Given** der Lauf ist nicht `merged`, oder es wäre ein anderer Branch als der Basis-Branch betroffen, **When** gepusht werden soll, **Then** wird abgelehnt.

### User Story 2 – Orchestrator-Ablauf nach Stufe (Priority: P1)

Der Skill `sak-pipeline` führt nach `approved` automatisch `run merge` aus. Bei `after_merge` folgt danach automatisch `run push`. Der Abschlussbericht nennt Merge-Commit, Push-Ergebnis und, je nach `autonomy.deploy`, die Frage nach dem Deploy oder den Hinweis „Deploy nur manuell“.

### User Story 3 – Deploy nach OK (Priority: P2)

`autonomy.deploy` hat die Werte `after_approval` (Default, wie bisher: Orchestrator nach ausdrücklichem OK) und `never` (Orchestrator deployt nie, nur der Betreiber selbst). Nach dem Deploy setzt der Orchestrator den Commit-Marker `deploy(NNN): …`. Bei `push: after_merge` pusht er den Marker ebenfalls über `sak run push`.

## Requirements *(mandatory)*

- **FR-001**: Contract-Erweiterung von `sak.config/1`:
  - optional `autonomy: {push: manual|after_merge, deploy: after_approval|never, remote: string}`
  - Defaults: `push: manual`, `deploy: after_approval`, `remote: origin`
- **FR-002**: Contract-Erweiterung von Vokabular und Event: neue Ereignisart `run.pushed` mit `data: {remote, branch, commit}`, DE-Label „Gepusht“. Ein Lauf-Zustand kommt nicht hinzu (Push ändert den Zustand `merged` nicht).
- **FR-003**: `sak run push <run>` nach US1:
  - `git push <remote> <base_branch>:<base_branch>`, ohne `--force`, ohne Tags
  - Timeout 60 s
  - Ausgabe ohne Zugangsdaten
  - erlaubt auch für Marker-Commits nach dem Merge desselben Laufs (HEAD des Basis-Branch muss den Merge-Commit enthalten)
- **FR-004**: Das Settings-Fragment bleibt bei `deny: Bash(git push)`. Der Push über `sak` ist durch die Allowlist `uv run … sak *` bzw. den Starter gedeckt.
- **FR-005**: Skill `sak-pipeline` nach US2 und US3. Er erzeugt keine Rückfrage an den Betreiber, wenn die Stufe den Schritt automatisch erlaubt.
- **FR-006**: Board und Dashboard: Das Event `run.pushed` erscheint in der Lauf-Ansicht (Event-Log), der Lauf zeigt „gepusht“ als Zusatz. Ein „Push abgelehnt“ erscheint als Aufmerksamkeitseintrag der Art `escalation` mit Gate `release`, ohne Zustandswechsel. Eine neue Gate-Art ist nicht nötig.
- **FR-007**: Vorlage `config.yml`: `autonomy` kommentiert mit Default `manual`. Beispiel ImmoAgent: `push: after_merge`.
- **FR-008**: Kit-Version 0.3.0.

## Success Criteria *(mandatory)*

- **SC-001**: Ein Lauf in einem Fixture-Repo mit Bare-Remote durchläuft approved → merged → pushed ohne Rückfrage. Das Remote enthält danach den Merge-Commit.
- **SC-002**: Non-fast-forward, falscher Branch, Stufe `manual` und Lauf nicht `merged` werden jeweils mit verständlicher Meldung abgelehnt. Alle Fälle sind getestet.
