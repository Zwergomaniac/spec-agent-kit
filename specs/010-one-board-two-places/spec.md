# Feature Specification: Ein Board, zwei Orte

**Feature Branch**: `010-one-board-two-places`

**Created**: 2026-10-21

**Status**: Planned

**Input**: Feedback des Betreibers vom 2026-10-21 beim sak-Trial in ImmoAgent. Er hat das lokale Board und specboard.prozessfit.de nebeneinander verglichen:
- Das lokale Board und das Online-Board sehen völlig verschieden aus. Erwartet war dasselbe Design, lokal nur ohne Portfolio.
- Das Online-Board zeigt für ImmoAgent keinen Lauf. Das alte ImmoAgent-Board zeigt dagegen den letzten Lauf der alten Pipeline (088, abgebrochen, Eskalation gelöst).
- Die Kennzahlen weichen ab: Blockiert 4 ↔ 0, Abgeschlossen 61 ↔ Fertig 69, Wartet 12 ↔ 19.
- Der Ticker online ist fast leer, ohne Betreff und ohne Hover-Details.

Ursachenanalyse (2026-10-21):
- Das lokale Board des Kits (`sak board serve`, Spec 006 FR-008) ist ein Nachbau des alten ImmoAgent-HTML, nicht die Dashboard-UI. Das war eine bewusste, aber falsche Annahme.
- In ImmoAgent laufen zwei Pipelines mit getrennter Historie: alt `.specify/pipeline/events.jsonl`, neu `.spec-agent/state/`. sak importiert die alte Historie nicht.
- „Blockiert“ und „Entscheidung“ kommen im alten Board aus `blockers.yml` und `deferred-decisions.md`. Im Kit sind sie ein Plugin, das es noch nicht gibt.
- „Fertig“ und „Freigabe“ sind im Kit anders definiert (Spec 001 FR-006, Spec 006 FR-003/FR-006). Die UI erklärt die Definitionen nicht.
- `share_commit_subjects: false` ist Default, deshalb hat der Ticker online keinen Text. Ein Hover mit Details existiert nicht.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Lokal dasselbe Board wie online (Priority: P1)

`sak board serve` zeigt im Zielprojekt dieselbe Projektansicht wie das zentrale Dashboard, mit gleichem Design, gleichen Tabs (Board, Läufe, Aufmerksamkeit, Konflikte) und gleicher Lauf-Ansicht. Es gibt kein Portfolio, kein Admin und keinen Login. Die Daten kommen direkt aus dem Repo. Node braucht das Zielprojekt dafür nicht.

**Acceptance Scenarios**:
1. **Given** ein Zielprojekt mit Kit, **When** `.spec-agent\sak board serve --open` läuft, **Then** öffnet sich die Projektansicht im Design des Dashboards. Deep Links auf Tabs und Läufe funktionieren lokal ebenso.
2. **Given** dasselbe Board-Dokument lokal und online, **When** beide Ansichten verglichen werden, **Then** sind Inhalt und Darstellung gleich. Ausnahme ist der Ticker-Text, solange er nicht geteilt wird: Lokal ist er immer sichtbar.

### User Story 2 – Ticker mit Inhalt und Details (Priority: P1)

**Acceptance Scenarios**:
1. **Given** ein Ticker-Eintrag, **When** man mit der Maus darüberfährt oder ihn fokussiert, **Then** erscheinen der kurze Commit-Hash, die Zeit, die betroffene Spec und der Betreff (sofern geteilt).
2. **Given** `share_commit_subjects: true`, **When** gepusht wird, **Then** zeigt auch das Online-Board die Betreffe.
3. Für ImmoAgent und AI-Forge wird `share_commit_subjects: true` gesetzt. Die Vorlage für fremde Projekte behält `false`.

### User Story 3 – Kennzahlen sind erklärt (Priority: P2)

Jede Kennzahl-Kachel und jede Spaltenüberschrift hat einen Tooltip mit ihrer Definition, zum Beispiel „Fertig = Station Umsetzung fertig, Deploy oder Live geprüft“ oder „Freigabe = Taskliste vorhanden, keine Task erledigt, nie ein Lauf gestartet“.

### User Story 4 – Alte Lauf-Historie übernehmen (Priority: P2)

Ein einmaliger, wiederholbarer Import überführt die Lauf-Historie einer bestehenden ImmoAgent-Pipeline (`.specify/pipeline/events.jsonl`, `runs/<spec>/run.json`) in das Format des Kits. Die Zuordnung folgt Spec 001 Anhang A. Danach zeigen lokales und Online-Board auch die alten Läufe, etwa 066, 084, 085, 088 und 092.

**Acceptance Scenarios**:
1. **Given** die 47 alten Events von ImmoAgent, **When** der Import läuft, **Then** entstehen gültige v1-Events und Läufe mit stabilen Lauf-IDs. Ein zweiter Import erzeugt keine Duplikate.
2. **Given** ein alter „geparkter“ Lauf (`aborted` nach API-Limit), **When** importiert wird, **Then** bleibt er `aborted`. Es gibt keine Umdeutung, weil `paused` damals nicht existierte.

### User Story 5 – Blocker und Entscheidungen als erstes Plugin (Priority: P2)

Ein Plugin liest `blockers.yml` und `deferred-decisions.md` im Format von ImmoAgent. Es erzeugt Aufmerksamkeitseinträge der Art `blocker` bzw. `decision` und setzt `blocked` an den Specs. Aktiviert wird es per `plugins:` in der Config.

**Acceptance Scenarios**:
1. **Given** ImmoAgent mit aktivem Plugin, **When** das Board entsteht, **Then** stimmt „Blockiert“ mit dem alten Board überein, sofern die Definitionen gleich sind. Abweichungen werden im Board als Hinweis erklärt.

### User Story 6 – Board-Ableitung angleichen (Priority: P1)

Herkunft: sak-Trial ImmoAgent, Befund 5 (Bericht vom 2026-10-21). Gefunden wurden diese Abweichungen gegenüber dem alten `dev_board.py`, bei 94 identischen Specs:

1. `[~]` (teilweise erledigt) wird nicht gezählt. Betroffen sind 018 und 048.
2. `descoped` wird nur aus `**Status**: Descoped` in spec.md gelesen. ImmoAgent führt es in `.specify/feature-status.yml`. Die Quelle soll konfigurierbar sein bzw. über ein Plugin kommen. Betroffen sind 026, 030, 052, 054 und 076.
3. `**[Betreiber]**` in einem Code-Span wird fälschlich als Betreiber-Aufgabe erkannt (092 T038/T039). Außerdem gehen Code-Spans im angezeigten Grund verloren.
4. Eine Folgezeile einer Aufzählung, die mit ```` ``` ```` beginnt, wird als Codeblock gelesen und verschluckt die übrigen Tasks (091: 0/2 statt 0/10).
5. Task-Zeilen werden anders erkannt als im alten Board: Aufzählungsvarianten, Großschreibung, Unteraufgaben. Betroffen sind 038 und 063. Zielregel festlegen und dokumentieren.
6. Die Station `deployed` mit offenen Tasks zählt als „fertig“ (066: 50/52). Klären, ob „fertig“ an der Station oder an den Tasks hängt.
7. Die Textausgabe (`sak board --text`) zeigt Zeiten in UTC ohne Kennzeichnung. Sie soll lokale Zeit mit Zone zeigen.

**Acceptance**: Für ImmoAgent stimmen die Kennzahlen mit dem alten Board überein, bis auf bewusst andere Definitionen. Jede verbleibende Abweichung ist in der UI erklärt (US3). Für jeden der 7 Punkte gibt es einen Regressionstest mit minimalem Fixture.

## Clarifications

### Session 2026-10-21 (Planer, Defaults nach Betreiber-Auftrag „alles Offene abarbeiten“)

- Q: Wie kommt die UI in die vendorte Engine? → A: `apps/dashboard-web` bekommt ein Build-Ziel `build:local`, das nach `packages/engine/src/spec_agent_kit/board/web/` baut. Das Ergebnis wird eingecheckt wie generierte Contracts, `pnpm board:check` prüft die Aktualität. Es ist Teil der Engine und wird deshalb über Lock/Upgrade verteilt. Das alte `static/board.html` entfällt.
- Q: Events im lokalen Modus? → A: Ja. `sak board serve` bedient dieselben Lese-Endpunkte wie das Dashboard (Teilmenge, ohne Auth). Die UI erkennt den lokalen Modus über `/api/meta` (`mode: "local"`).
- Q: Import Kern oder Plugin? → A: Kernbefehl `sak migrate legacy-pipeline`, weil das Format der Ursprung des Kits ist (ImmoAgent 093). Ohne `--apply` zeigt er nur einen Plan.
- Q: Contract `plugins`? → A: Rückwärtskompatible Erweiterung von `sak.config/1`: `plugins` wird eine Liste von `{name, options?}` mit Enum-Namen; erstes Plugin `legacy-status`.
- Q: Altes ImmoAgent-Board abschalten? → A: Nein, es bleibt bis zur Rückmigration.
- Q: „Fertig“ bei `deployed` mit offenen Tasks (US6 Punkt 6)? → A: Die Station bleibt `deployed` (Marker ist ein Fakt). Für Kennzahlen gilt eine Spec als fertig erst bei Station ≥ `implemented` UND 0 offenen bzw. teilweisen Tasks, sonst als „in Arbeit“.
- Q: `[~]`? → A: Die Board-Ableitung zählt es als neues optionales Feld `tasks.partial`, also nicht erledigt und nicht offen (Contract-Erweiterung, wie in ImmoAgent 092).

## Requirements *(mandatory)*

- **FR-001** (US1): `sak board serve` liefert die gebaute Dashboard-UI aus. Es stellt diese Endpunkte bereit, jeweils mit gleicher Form wie das zentrale Dashboard:
  - `GET /api/meta` (zusätzlich `mode: "local"`, `project_key`)
  - `GET /api/projects/<key>` (Board live gebaut, höchstens alle 2 s neu)
  - `GET /api/projects/<key>/runs/<runId>`
  - `GET /api/projects/<key>/events?run=&since=&limit=`

  Loopback und Host-Prüfung bleiben. Die UI zeigt im lokalen Modus kein Portfolio, keinen Admin-Bereich und keinen Login. Die Startroute ist `#/project/<key>`.
- **FR-002** (US1): Gleiche Darstellung lokal und online. Lokal ist der Ticker-Text immer sichtbar.
- **FR-003** (US2): Contract-Erweiterung: optionales `ticker[].commit` (7–40 hex). Der Collector füllt es mit dem kurzen Hash. Die UI zeigt per Hover oder Fokus Hash, lokale Zeit, Spec und Betreff (falls vorhanden). Die Beispiel-Configs für ImmoAgent und AI-Forge setzen `share_commit_subjects: true`, die Vorlage bleibt bei `false`.
- **FR-004** (US3): Jede Kennzahl-Kachel und jede Spaltenüberschrift hat einen Tooltip mit der Definition. Die Texte stehen zentral in der Web-App und entsprechen Spec 006 FR-006 sowie dieser Spec.
- **FR-005** (US4): `sak migrate legacy-pipeline [--source <dir>] [--apply]` liest `<dir>/events.jsonl` und `<dir>/runs/*/run.json` (Default `.specify/pipeline`) und erzeugt v1-Events und Läufe unter `.spec-agent/state/`, nach Spec 001 Anhang A.
  - Lauf-ID aus Spec-Nummer und Zeit von `run_started`.
  - Event-IDs deterministisch aus Inhalt und Zeit, damit ein Import idempotent ist und keine Duplikate am Dashboard entstehen.
  - `aborted` bleibt `aborted`.
  - Unbekannte Arten werden gezählt und gemeldet.
- **FR-006** (US5): Plugin `legacy-status`, aktiviert per `plugins: [{name: legacy-status}]`. Es liest:
  - `.specify/blockers.yml` → `blocker`-Einträge und `specs[].blocked`
  - `.specify/deferred-decisions.md` → `decision`-Einträge
  - `.specify/feature-status.yml` → descoped

  Formate wie bei ImmoAgent (Referenz: `ImmoAgent/.specify/scripts/python/feature_status.py`). Fehlt eine Datei, folgt ein Hinweis in `notes`, kein Fehler.
- **FR-007** (US6): Die Parser-Regeln aus US6 Punkt 1–7 werden umgesetzt und in `docs/architecture.md` als „Board-Ableitungsregeln“ dokumentiert. Task-Zeile ist jede Markdown-Aufzählung (`-`, `*`, `+`, nummeriert, auch eingerückt) mit Checkbox `[ ]`, `[x]`, `[X]` oder `[~]`. Codeblöcke beginnen nur mit einem Fence am Zeilenanfang nach höchstens 3 Leerzeichen und nicht als Fortsetzung einer Aufzählung. Code-Spans werden für Marker-Erkennung ignoriert, im angezeigten Grund aber erhalten.

## Success Criteria *(mandatory)*

- **SC-001**: Lokales und Online-Board sind bei gleichem Board-Dokument visuell gleich (Screenshot-Vergleich der Projektansicht).
- **SC-002**: Für ImmoAgent zeigt das Kit nach Import und mit Plugin dieselben Läufe und Blocker wie das alte Board. Jede verbleibende Kennzahl-Abweichung ist durch einen Tooltip oder Hinweis erklärt.
- **SC-003**: Jeder Ticker-Eintrag hat per Hover oder Fokus einen Hash und eine Zeit.

## Assumptions

- Das alte ImmoAgent-Board und die alte Pipeline bleiben während des Trials unverändert in Betrieb.
- Commit-Betreffe gelten als Metadaten (Constitution II). Teilen bleibt eine Entscheidung je Projekt.
