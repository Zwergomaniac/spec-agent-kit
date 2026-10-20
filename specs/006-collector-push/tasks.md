# Tasks: Collector, lokales Board und Push

**Input**: [spec.md](spec.md), [plan.md](plan.md), Specs 001–004. Die Referenz `ImmoAgent/.specify/scripts/python/dev_board.py` und `ImmoAgent/.specify/dev-board/index.html` wird nur gelesen.

## Phase 1: Fixture

- [X] T001 `tests/fixtures/board_repo/` mit einem Generator für ein deterministisches Fixture-Repo nach Spec US1 (Independent Test).

## Phase 2: US1 – Board-Ableitung

- [X] T002 `board/git_history.py` (Port).
- [X] T003 `board/specs.py` (FR-001, FR-002, FR-003 Spec-Teil).
  - Anmerkung: `approval` entsteht nur bei Taskliste mit mindestens einer Task (0/0 hat nichts zum Freigeben, Spec 001 Randfälle). Eine offene Klärung unterdrückt `approval` derselben Spec und gibt `waiting: clarification` (wie in der Referenz, `elif`). Klärungsabschnitt = `## Clarifications` oder `## Klärung(en)`. Betreiber-Task-Gründe sind der Tasktext ohne die Kennzeichnung. Specs ohne `spec.md` (nur plan/tasks) bekommen die Station `null`.
- [X] T004 `board/runs_view.py` (FR-004, `escalation`- und `stale_run`-Einträge).
  - Anmerkung: Eine Eskalation bleibt offen, solange der Lauf `escalated` ist (auch `paused` aus `escalated`). Läufe ohne Event nutzen `updated_at` als `last_event_at`. Hook-lose Urteile (`verdict.recorded` ohne Station) ergänzen eine fertige Station mit dem Agent-Namen aus der Config.
- [X] T005 `board/build.py` (FR-005 bis FR-007; `notes` bei Fehlern, nie abstürzen).
  - Anmerkung: Ungültige Listeneinträge (z. B. Lauf mit unbekanntem Zustand aus einem anderen Kit-Stand) werden verworfen und als Hinweis gemeldet; jeder andere Verstoß ist ein `BoardError` mit Pfad (Exit 1). `metrics.blocked` ist in v1 immer 0 (Blocker kommen über Plugins). Es gibt höchstens 100 Marker im Dokument.
- [X] T006 CLI `sak board [--json|--text]`, `board/text.py`.
  - Anmerkung: `sak board` und `--text` zeigen den Commit-Betreff lokal immer (Spec Annahmen); der Push übernimmt `dashboard.share_commit_subjects`.
- [X] T007 Golden-File-Test und Einzeltests (Marker vor dem Task-Commit, unlesbare Datei, abgeschaltete Stationen, descoped, Betreiber-Task, Klärung im Code-Span ignoriert).

## Phase 3: US2 – Lokale Ansicht

- [X] T008 `board/serve.py` und `static/board.html` (Port der Referenz-HTML auf `sak.board/1`, Labels de eingebettet aus `labels/de.json`). Tests für Host-Prüfung, 404 und 405.
  - Anmerkung: Der Server nutzt kein `SO_REUSEADDR` (unter Windows würde es einen zweiten Server auf demselben Port zulassen); belegte Ports ergeben Exit 2. `HEAD` gilt wie jede Nicht-GET-Methode als 405 (Spec: nur `GET`). Die Labels kommen über die neue Funktion `contracts.labels(locale)`; die Seite bekommt zusätzlich eine CSP und `X-Frame-Options: DENY`. Pfade mit Query-String werden auf den Pfad reduziert.

## Phase 4: US3 – Push

- [X] T009 `push/outbox.py` (Cursor, Reset, kaputte Zeilen).
  - Anmerkung: Identität = Hash der ersten vollständigen Zeile; Reset bei Offset > Dateigröße oder anderer Identität. Eine halbe Zeile am Dateiende (ohne Zeilenumbruch) wartet. Vertragswidrige Zeilen werden wie kaputte übersprungen und gezählt (`skipped` im Cursor, Hinweis im Board). Batches sind zusätzlich auf 1,2 MB begrenzt, damit die Anfrage unter 2 MB bleibt (500 Events × 8 KB wären mehr).
- [X] T010 `push/client.py` und `push/run.py` (FR-009, FR-012, Abgelehnt-Protokoll).
  - Anmerkung: Auslegung von „400 je Event“: Das Dashboard antwortet auf Einzelfehler mit 200 und `rejected[]` (so in `apps/dashboard-api`); diese Einträge gehen ins Abgelehnt-Protokoll (nur Event-ID und Grund, nie der Inhalt) und der Cursor rückt vor. Ein 400 auf die ganze Anfrage ist systemisch (nie eventbezogen): Cursor bleibt, Ursache wird gemeldet; „unsupported schema version“ und „unknown event type“ (auch je Event) gelten als Versionsfehler, Cursor bleibt. Board-Ablehnungen (`board: …`) blockieren die Events nicht. Das Board geht nur mit der Anfrage, die den Rückstand leert, und nur bei geändertem Inhalt (Hash ohne `generated_at`). Der Client folgt keinen Weiterleitungen (Schlüsselschutz), nutzt für Loopback keinen Proxy und nimmt `http://` nur für `localhost` und `127.0.0.1`. Netzfehler enden mit Exit 1 (Status `unreachable`).
- [X] T011 `spawn_background` und Sperrdatei (FR-010). Auslöser in Hooks und Run-Befehlen (FR-011).
  - Anmerkung: Der Hintergrundprozess startet `python -m spec_agent_kit.cli push --quiet` mit `sys.executable`. Der Start wird übersprungen, solange die Sperre frisch ist. Auslöser (nur bei `push: auto` und gesetzter URL): nach `sak hook …` und nach jedem `sak run …`/`sak event …` außer `list`, `show`, `snapshot`, auch bei Ablehnung (Events könnten entstanden sein).
- [X] T012 CLI `sak push`.
  - Anmerkung: `sak push` ohne Flag läuft im Vordergrund (Exit 0 bei Erfolg, deaktiviert und gesperrt; 1 bei Fehler); `--background` startet losgelöst, `--quiet` unterdrückt die Ausgabe.
- [X] T013 Push-Tests (SC-002, SC-003) mit einem lokalen Test-Server.
  - Anmerkung: Der Test des echten Hintergrundprozesses (SC-003) misst den Hook in-process und mit frischem Interpreter, beide unter 1 s.

## Phase 5: Abschluss

- [X] T014 Optionaler Test `SAK_IMMOAGENT_SPECS=<pfad>` (SC-001). Alles grün. README-Statusmatrix: Collector/Ingest → implementiert (Collector-Seite).
  - Anmerkung: Der Test erwartet das Projekt-Repo (nicht nur `specs/`) und liest es ohne Schreibzugriff (In-Memory-Config, `git status` vor und nach dem Lauf identisch). Lokaler Lauf gegen ImmoAgent: 94 Specs, gültiges Board ohne Ausnahme und ohne Hinweise.
