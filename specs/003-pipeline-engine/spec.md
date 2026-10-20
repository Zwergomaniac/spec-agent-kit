# Feature Specification: Pipeline-Engine (generalisiert aus ImmoAgent 093)

**Feature Branch**: `003-pipeline-engine`

**Created**: 2026-10-20

**Status**: Implemented

**Input**: ADR 0001 E1, E7–E9, Constitution VI. Referenz-Implementierung:
- `ImmoAgent/.specify/scripts/python/pipeline.py` (583 Zeilen, 40 Tests in `tests/unit/specify/test_pipeline.py`)
- `ImmoAgent/.claude/skills/speckit-pipeline/SKILL.md`
- `ImmoAgent/.claude/agents/pipeline-*.md`
- `ImmoAgent/specs/093-agent-pipeline/` (spec, contracts, evaluation)

## Ziel

Die erprobte Pipeline wird als Teil der CLI `sak` übernommen. Dabei wird sie generalisiert:
- Rollen kommen aus der Config (Spec 004).
- Lauf-IDs ersetzen den Spec-Namen als Schlüssel, die Historie bleibt (Spec 001).
- Events nutzen die v1-Hülle (Spec 002).
- Der neue Zustand `paused` ersetzt das Parken über `aborted`.
- Verwaiste Läufe werden erkannt und können übernommen werden.
- Die Engine ist plattformneutral.

Agents und Orchestrator-Skill kommen als generische Vorlagen dazu.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Freigegebene Spec läuft vollständig durch (Priority: P1)

Der Betreiber sagt „umsetzen“ für Spec 012. Der Orchestrator-Skill führt diesen Ablauf aus:
1. preflight
2. Builder
3. guard
4. snapshot
5. alle aktiven Prüfer parallel
6. reviewer-check
7. verdict je Prüfer
8. combine
9. Merge `--no-ff` in den Basis-Branch, ohne Push
10. Abschlussbericht

**Independent Test**: In einem Test-Repo (Fixture) spielt ein Skript die Befehle mit vorgefertigten Prüfer-Antworten durch. Der Lauf endet mit `merged`. Die Event-Folge entspricht Spec 002.

**Acceptance Scenarios**:

1. **Given** beide Prüfer urteilen `approve`, **When** `combine` läuft, **Then** ist der Lauf `approved`, und `sak run merge` erzeugt einen Merge-Commit mit `run.merged`.
2. **Given** Runde 1 ergibt `changes_requested` und `max_rounds` ist 2, **When** `combine` läuft, **Then** wechselt der Lauf nach `building`, Runde 2, mit der Liste der Muss-Befunde in der Ausgabe.
3. **Given** Runde 2 ergibt `changes_requested`, **When** `combine` läuft, **Then** ist der Lauf `escalated` mit Gate `round_limit`.

### User Story 2 – Schutz greift mechanisch (Priority: P1)

**Acceptance Scenarios**:

1. **Given** der Builder hat `.claude/settings.json` geändert, **When** `guard` läuft, **Then** folgt `escalate: true` mit Gate `protected_paths`. Prüfer werden nicht gestartet.
2. **Given** ein Prüfer hat eine Datei verändert, **When** `reviewer-check` läuft, **Then** wird der Lauf `escalated` mit Gate `review_integrity`.
3. **Given** der Arbeitsstand ist nicht sauber, **When** `preflight` läuft, **Then** wird mit der Liste der Dateien abgelehnt.

### User Story 3 – Pausieren, Fortsetzen, Übernehmen (Priority: P1)

**Acceptance Scenarios**:

1. **Given** ein Lauf in `building` wird durch ein API-Limit unterbrochen, **When** der Orchestrator `sak run pause` aufruft, **Then** ist der Lauf `paused`, die Sperre ist frei, und ein anderer Lauf kann starten.
2. **Given** ein pausierter Lauf und kein aktiver Lauf, **When** `sak run resume` läuft, **Then** wird der Run-Branch ausgecheckt (bei sauberem Stand), und der Lauf kehrt in den Zustand vor der Pause zurück.
3. **Given** ein aktiver Lauf ohne Event seit mehr als `stale_hours`, **When** `preflight --takeover "Grund"` für eine andere Spec läuft, **Then** wird der alte Lauf `aborted` (Event `run.taken_over` mit Grund), und der neue startet.

### User Story 4 – Nur-Prüfung (Priority: P2)

Für bereits umgesetzte Arbeit, etwa aus der Hauptsitzung: `sak run preflight <spec> --review-only --base <commit>` legt einen Lauf der Art `review_only` im Zustand `reviewing` an. Es gibt keinen Branch-Wechsel und keinen Builder. `combine` schließt ihn bei `approve` als `reviewed`, sonst als `escalated`.

### User Story 5 – Hooks melden Stationen (Priority: P1)

Die Hooks `SubagentStart` und `SubagentStop` rufen `sak hook subagent-start|subagent-stop` auf. Die Engine ordnet den Agent-Namen über die Config einer Rolle zu und schreibt `station.started` bzw. `station.finished` mit Dauer. Hooks enden immer mit Exit 0 und blockieren nie.

### Edge Cases

- **Hook-Payload ohne Agent-Typ:** einmalig ein Event `diag.hook` mit den Schlüsseln, danach still.
- **Hook ohne aktiven Lauf:** kein Event.
- **Ungültiges Prüfer-Urteil:** Ablehnung mit Grund. Der Orchestrator fordert einmal neu an, danach gilt `needs_human` mit Gate `review_integrity` und Grund „Urteil ungültig“.
- **Bestehender Spec-Branch enthält den Basis-HEAD nicht:** Ablehnung mit Hinweis. Kein automatisches Rebase.
- **Windows-Konsole mit cp1252:** Ausgaben mit Umlauten und `→` funktionieren trotzdem.
- **Prüfer-Artefakte** (Screenshots, Playwright-Ausgaben): nur unter `.spec-agent/state/runs/<run_id>/`. Sie zählen nicht als Repo-Änderung.

## Requirements *(mandatory)*

### Functional Requirements

**CLI**

- **FR-001**: Die Engine MUSS als Unterbefehle der CLI `sak` bereitstehen. Konventionen siehe `docs/architecture.md`: JSON auf stdout; Exit 0, 1 oder 2; Hooks immer 0. Befehle:
  - `config check|show` (Spec 004)
  - `run preflight <spec> [--base <branch>] [--review-only --base-commit <sha>] [--takeover "<grund>"]`
  - `run state <run> <zustand> [--reason] [--gate]`
  - `run pause <run> [--reason]`
  - `run resume <run>`
  - `run release <run> [--reason]` (→ `approved`)
  - `run return <run> --reason` (→ `building`, nächste Runde, nur unterhalb des Rundenlimits)
  - `run abort <run> [--reason]`
  - `run guard <run>`
  - `run snapshot`
  - `run reviewer-check <hash>`
  - `run verdict <run> <role> <datei>`
  - `run combine <run>`
  - `run merge <run>`
  - `run list [--all]`
  - `run show <run>`
  - `hook subagent-start|subagent-stop` (stdin)
  - `event emit <type> [--run] [--reason]` (für Ereignisse ohne Befehl)
- **FR-002**: `<run>` MUSS eine Lauf-ID, ein Spec-Verzeichnis oder eine Spec-Nummer akzeptieren. Bei Spec-Angabe wird der jüngste nicht beendete Lauf dieser Spec gewählt.

**Zustand und Speicher**

- **FR-003**: Der Laufzustand MUSS in `.spec-agent/state/runs/<run_id>/run.json` liegen:
  - `run_id`, `spec`, `kind`, `state`, `paused_from`
  - `round`, `max_rounds`
  - `branch`, `base_branch`, `base_commit`
  - `started_at`, `updated_at`
  - `escalation{reason, gate, round}`
  - `origin{branch}`

  Daneben liegen die Dateien `verdict-<role>-r<n>.md`, `open-stations.json` und Prüfer-Artefakte. Der Ordner `.spec-agent/state/` ist gitignored.
- **FR-004**: Zustandswechsel MÜSSEN die Übergangstabelle aus Spec 001 FR-011 erzwingen. Jeder Wechsel schreibt das passende Event aus Spec 001 FR-022 als v1-Event (Spec 002) nach `.spec-agent/state/events.jsonl`. Geschrieben wird nur angehängt, zeilenweise und mit `flush`.
- **FR-005**: Die Sperre MUSS Spec 001 FR-013 umsetzen: höchstens ein Lauf in `building`, `reviewing`, `approved` oder `escalated`. `paused` belegt die Sperre nicht. Verwaist ist ein Lauf, dessen letztes Event älter als `stale_hours` ist. Ein verwaister Lauf wird bei jedem `preflight` genannt und nur mit `--takeover` beendet.

**Ablauf**

- **FR-006**: `preflight` MUSS prüfen:
  - Config gültig
  - Arbeitsstand sauber, ohne `clean_ignore` und `.spec-agent/state/`
  - `specs/<spec>/tasks.md` existiert
  - Sperre frei

  Danach legt es den Branch nach `branch_pattern` an oder wechselt auf ihn und schreibt `run.started` und `round.started`. Die Antwort enthält Lauf-ID, Branch, Basis, `max_rounds`, aktive Rollen mit Agent-Namen und die Befehle aus `commands`.
- **FR-007**: `guard` MUSS die Pfade aus `base_commit..HEAD` und dem Arbeitsstand gegen Kern-Schutz und `guard.protected_paths` prüfen (Treffer → `escalate: true`, Gate `protected_paths`). Gegen `escalation.paths` wird ebenfalls geprüft, Treffer werden nur als `hints` ausgegeben.
- **FR-008**: `snapshot` MUSS einen SHA-256 über HEAD, die geänderten Dateien und `git diff` bilden, jeweils ohne `clean_ignore`. `reviewer-check` vergleicht damit.
- **FR-009**: `verdict` MUSS das Urteilsformat prüfen:
  - **Erste Zeile:** `Verdict: approve|changes_requested|needs_human`. Bei Locale `de` ist zusätzlich `Urteil: OK|Änderung|Mensch prüft` erlaubt.
  - **Grund:** `Reason:` oder `Grund:` in den Zeilen 2–4, Pflicht bei `changes_requested` und `needs_human`.
  - **Befunde:** `- [must|may] datei:zeile — … → …`. Bei `de` sind auch `[Muss]` und `[Kann]` erlaubt.
  - **Regeln aus Spec 001 FR-018:** `approve` mit `must` zählt als `changes_requested`, `changes_requested` ohne `must` ist ungültig.

  Das Urteil wird als `verdict-<role>-r<round>.md` abgelegt. `verdict.recorded` enthält `must_count` und `may_count`.
- **FR-010**: `combine` MUSS das Gesamturteil nach Spec 001 FR-019 bilden, und zwar über alle aktiven Prüfrollen der Runde. Fehlt das Urteil einer aktiven Rolle, wird abgelehnt. Bei `changes_requested` unterhalb des Rundenlimits gibt `combine` die Muss-Befunde im Wortlaut aus, als Eingabe für den Builder der nächsten Runde.
- **FR-011**: `merge` MUSS bei Zustand `approved` und sauberem Stand Folgendes tun:
  - auf den Basis-Branch wechseln
  - `git merge --no-ff <branch> -m "merge: <spec> via sak pipeline (<run_id>)"`
  - `run.merged` mit `merge_commit` schreiben

  Es pusht nie. Bei einem Merge-Konflikt bricht es den Merge ab (`git merge --abort`) und eskaliert.

**Hooks**

- **FR-012**: `hook subagent-start|stop` MUSS:
  - den Agent-Typ aus `agent_type`, `subagent_type` oder `tool_input.subagent_type` lesen
  - den Typ über die Config auf eine Rolle abbilden
  - die Startzeit in `open-stations.json` führen
  - `station.started` bzw. `station.finished` mit `duration_s` schreiben
  - bei jedem Fehler still mit Exit 0 enden
  - in höchstens 2 s fertig sein

  Er DARF keinen Netzwerkzugriff machen. Der Push ist Sache von Spec 006.

**Vorlagen (installiert durch Spec 005)**

- **FR-013**: Unter `packages/agent-blueprint/templates/claude/` MÜSSEN liegen:
  - `agents/sak-builder.md`, `sak-code-reviewer.md`, `sak-ui-reviewer.md`, `sak-security-reviewer.md`, `sak-docs.md`
  - `skills/sak-pipeline/SKILL.md` (Orchestrator)
  - `settings.fragment.json`: Hooks plus Permissions-Default nach Constitution IV

  Die Vorlagen sind generalisiert aus ImmoAgent und enthalten keine Projektwerte (Spec 004 SC-001). Sie sind in Locale `de` geschrieben. Agents lesen Befehle, Pfade, Regeln und Themen aus `sak config show`.
- **FR-014**: Der Orchestrator-Skill MUSS Folgendes sicherstellen:
  - **Freigabe:** Er startet nur nach ausdrücklichem „umsetzen“ für genau diese Spec.
  - **Arbeitsweise:** Er schreibt selbst keinen Code und startet Prüfer parallel in einer Nachricht.
  - **Ablauf:** Er folgt FR-006 bis FR-011.
  - **Unterbrechungen:** Bei API-Limit oder Unterbrechung ruft er `run pause` auf. Bei Eskalation stoppt er und wartet auf den Betreiber.
  - **Abschluss:** Am Ende kommt ein kurzer Bericht auf Deutsch („noch nicht deployt“).
  - **Deploy:** nur auf ausdrückliche Anweisung mit `deploy.command`, danach Commit-Marker `deploy(NNN): …`.
  - **Graphify:** keine graphify-Pflicht, das ist ein Plugin.
- **FR-015**: `settings.fragment.json` MUSS enthalten:
  - **Hooks:** `SubagentStart` und `SubagentStop` mit Matcher auf `sak-.*`. Befehl: `uv run --project "$CLAUDE_PROJECT_DIR/.spec-agent/engine" sak hook subagent-start || true`, Timeout 5.
  - **Permissions:** Allowlist für `uv run --project .spec-agent/engine sak *`, `git status|diff|log` (Merge und Branch-Wechsel nur über `sak run`, nie direkt freigegeben) und die Testbefehle des Projekts. Die Testbefehle trägt Spec 005 beim Init ein.
  - **Deny:** `git push`, `git push *`, Lesen und Schreiben von `.env*` und `.spec-agent/dashboard.key`.
  - **Kein** `defaultMode: bypassPermissions`.

### Key Entities

Lauf, Runde, Station, Urteil, Snapshot (siehe Spec 001 und 002).

## Success Criteria *(mandatory)*

- **SC-001**: Alle 40 Verhaltensfälle der ImmoAgent-Tests (`test_pipeline.py`) sind als Tests übernommen und an das neue Modell angepasst, also mit Lauf-ID, Rollenliste und v1-Events. Dazu kommen Tests für pause, resume, takeover, review-only und merge.
- **SC-002**: Die komplette Testsuite läuft auf Windows und Linux grün (CI-Matrix).
- **SC-003**: Die Pilotfälle aus ImmoAgent (066 durchgelaufen, 084/085 eskaliert, 088 durch API-Limit unterbrochen) sind als End-to-End-Tests mit Fixture-Repo nachgestellt.
- **SC-004**: Vorlagen und Engine enthalten keinen ImmoAgent-Bezug (grep-Test auf `immoagent`, `owner_id`, `graphify`, `.venv/Scripts`).

## Assumptions

- Git ≥ 2.30 ist vorhanden. Alle Git-Aufrufe laufen über `subprocess` mit Argumentliste, nie über eine Shell.
- Der Spec-Branch-Name ist in v1 der Spec-Verzeichnisname (`branch_pattern: {spec}`). Mehrere Läufe einer Spec nutzen denselben Branch.
- Die UI-Messungen des UI-Prüfers (Überlauf, Tap-Ziele) bleiben Prompt-Wissen des Agents und werden nicht von der Engine erzwungen, wie in ImmoAgent.
