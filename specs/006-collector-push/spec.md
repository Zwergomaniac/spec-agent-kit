# Feature Specification: Collector, lokales Board und Push

**Feature Branch**: `006-collector-push`

**Created**: 2026-10-20

**Status**: Draft

**Input**: ADR 0001 E2. Referenz:
- `ImmoAgent/.specify/scripts/python/dev_board.py` (790 Zeilen)
- `ImmoAgent/.specify/dev-board/index.html`
- `ImmoAgent/specs/092-dev-dashboard/` (spec, data-model, stage2-draft)

## Ziel

Jedes Zielprojekt erzeugt sein Board-Dokument (`sak.board/1`) selbst aus Spec-Dateien, Git, Läufen und Events. Es gibt keine zweite Status-Quelle (ImmoAgent 092 FR-001). Das Board ist lokal ohne Netz sichtbar und wird ausfallsicher an das zentrale Dashboard gepusht.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Board-Dokument aus dem Repo (Priority: P1)

`sak board` gibt ein gültiges `sak.board/1` aus:
- Specs mit Station, Fortschritt, Wartegrund und Zeiten
- Aufmerksamkeitseinträge
- Läufe aus `.spec-agent/state/` mit Stationen und Urteilen
- Marker, Ticker, Kennzahlen, Hinweise

**Independent Test**: Ein Fixture-Repo mit 6 Specs in verschiedenen Stationen, Deploy- und Verified-Markern, einer offenen Klärung, einer Betreiber-Task, einem eskalierten und einem gemergten Lauf ergibt das erwartete Dokument (Golden File).

**Acceptance Scenarios**:

1. **Given** ein Commit `deploy(004): …` vor dem letzten Commit an `specs/004-*/tasks.md`, **When** das Board entsteht, **Then** ist die Station von 004 `implemented`, nicht `deployed`.
2. **Given** eine unlesbare `tasks.md`, **When** das Board entsteht, **Then** steht ein Hinweis in `notes`, und der Rest bleibt vollständig. Das Board stürzt nie ab.

### User Story 2 – Lokales Board ohne Netz (Priority: P2)

`sak board serve` zeigt das Board unter `http://127.0.0.1:5192`, nur Loopback, mit Host-Header-Prüfung und Aktualisierung alle 5 s. `sak board --text` gibt eine Kurzfassung mit höchstens 40 Zeilen für das Terminal aus.

### User Story 3 – Ausfallsicherer Push (Priority: P1)

Events und Board erreichen das Dashboard ohne Verlust und ohne Doppelungen. Die Pipeline wartet dabei nie auf das Netz.

**Acceptance Scenarios**:

1. **Given** das Dashboard ist nicht erreichbar, **When** 50 Events entstehen, **Then** bleiben sie lokal. Beim nächsten erfolgreichen Push kommen alle 50 an, und der Cursor rückt vor.
2. **Given** ein Hook läuft, **When** `push: auto` gesetzt ist, **Then** startet der Hook `sak push` als losgelösten Hintergrundprozess und endet selbst sofort. Ein zweiter gleichzeitiger Push wird über eine Sperrdatei verhindert.
3. **Given** das Dashboard lehnt einzelne Events ab (400), **When** die Antwort kommt, **Then** rückt der Cursor trotzdem vor. Die abgelehnten Events landen mit Grund in `.spec-agent/state/push-rejected.jsonl` und erscheinen als Hinweis im Board.
4. **Given** 401 oder ein Versionsfehler, **When** gepusht wird, **Then** bleibt der Cursor stehen, und `sak push` meldet die Ursache klar.

### Edge Cases

- **`dashboard.url` null oder `push: off`:** `sak push` meldet „deaktiviert“ mit Exit 0.
- **Schlüssel fehlt:** Exit 1 mit Hinweis auf `token_env` bzw. `.spec-agent/dashboard.key`.
- **Gekürzte oder kaputte Zeile in `events.jsonl`:** Sie wird übersprungen und gezählt (Hinweis). Keine Zeile wird doppelt gesendet.
- **`events.jsonl` wurde ersetzt** (kleiner als der Cursor-Offset): Der Cursor wird zurückgesetzt. Duplikate fängt das Dashboard über die `event_id` ab.

## Requirements *(mandatory)*

### Functional Requirements

**Board-Ableitung**

- **FR-001**: Die Stationen MÜSSEN nach Spec 001 FR-006 abgeleitet werden. Gelesen werden die Spec-Artefakte und ein einziger `git log`-Durchlauf (wie in der Referenzklasse `GitHistory`). Abgeschaltete Stationen (Spec 004 `stages`) werden nie vergeben.
- **FR-002**: Der Task-Fortschritt MUSS aus `tasks.md` kommen: `- [ ]` zählt als offen, `- [x]`/`- [X]` als erledigt. Eine Spec ist `descoped`, wenn ihr Kopf `**Status**: Descoped` enthält (Groß- und Kleinschreibung egal).
- **FR-003**: Aufmerksamkeitseinträge (Spec 001 FR-021) MÜSSEN so entstehen:

  | Art | Bedingung |
  |---|---|
  | `escalation` | je Lauf in `escalated` |
  | `stale_run` | je verwaistem aktivem Lauf |
  | `approval` | `tasks.md` vorhanden, 0 Tasks erledigt, nie ein Lauf gestartet, nicht descoped |
  | `clarification` | je Spec mit `[NEEDS CLARIFICATION:` außerhalb von Code-Spans |
  | `operator_task` | je offener Task mit `[operator]` oder `**[Betreiber]**` |

  `blocker` und `decision` entstehen in v1 nicht (Plugin).
- **FR-004**: Läufe MÜSSEN aus `runs/*/run.json` plus `events.jsonl` entstehen: Stationen, Urteile, Eskalationen, `last_event_at`, idle und stale. Ausgegeben werden höchstens 20 Läufe, die neuesten zuerst.
- **FR-005**: Marker und Ticker MÜSSEN aus den Commit-Betreffs kommen. Die Marker-Regex unterstützt Listen und Bereiche. Ticker-`text` gibt es nur bei `share_commit_subjects: true`.
- **FR-006**: Die Kennzahlen MÜSSEN so berechnet werden:
  - `in_progress`: Station `implementing`
  - `done`: Station `implemented` oder höher
  - `blocked`: Anzahl blockierter Specs
  - `waiting`: Anzahl der Aufmerksamkeitseinträge
  - `mean_lead_time_days`: aus erstem Spec-Commit bis Abschluss
- **FR-007**: Das Board-Dokument MUSS vor jeder Ausgabe gegen das Schema validiert werden. Ist es ungültig, folgt ein Fehler mit Pfad und Exit 1. Das wäre ein Bug.

**Lokale Ansicht**

- **FR-008**: `sak board serve [--port]`:
  - nur `127.0.0.1`
  - Host-Header-Prüfung (Loopback)
  - nur `GET /` und `GET /board.json`
  - eine einzelne HTML-Datei ohne externe Ressourcen, Rendering nur über `textContent`, Dark Mode per System
  - Spalten wie im Dashboard-Board

**Push**

- **FR-009**: `sak push [--quiet] [--background]` sendet die Events nach dem Cursor (`.spec-agent/state/push-cursor.json`: Byte-Offset und Datei-Identität) in Batches zu höchstens 500 Events. Dazu kommt das aktuelle Board als `sak.ingest/1` an `<dashboard.url>/api/ingest`. Timeout 3 s je Request, höchstens 3 Batches pro Aufruf.
- **FR-010**: `--background` MUSS sich vom aufrufenden Prozess lösen (Windows: `DETACHED_PROCESS`/`CREATE_NEW_PROCESS_GROUP`; POSIX: `start_new_session`) und sofort zurückkehren. Eine Sperrdatei mit Ablauf nach 60 s verhindert parallele Pushes.
- **FR-011**: Bei `push: auto` MÜSSEN `sak hook …` und die zustandsändernden `sak run …`-Befehle am Ende `sak push --background --quiet` auslösen. Fehler dabei werden ignoriert.
- **FR-012**: Der Push DARF nie andere Daten senden als validierte Events und das validierte Board (Constitution II). Er nutzt HTTPS, außer bei `http://localhost` oder `http://127.0.0.1` für die lokale Entwicklung.

### Key Entities

Board-Dokument, Push-Cursor, Abgelehnt-Protokoll.

## Success Criteria *(mandatory)*

- **SC-001**: Golden-File-Test des Fixture-Repos besteht. Dazu kommt ein Test gegen eine Kopie der ImmoAgent-`specs/` (nur lesen, als optionaler Test hinter Umgebungsvariable). Er erzeugt ein gültiges Board ohne Ausnahme.
- **SC-002**: Push-Tests gegen einen lokalen Test-Server decken ab: Erfolg, Netzfehler, 400 je Event, 401, Versionsfehler, Cursor-Reset, parallele Sperre.
- **SC-003**: `sak hook …` endet mit `push: auto` gegen ein nicht erreichbares Dashboard in unter 1 s.

## Assumptions

- Der Text der Commit-Betreffs wird standardmäßig nicht geteilt (Datenschutz). Lokal wird er immer angezeigt.
