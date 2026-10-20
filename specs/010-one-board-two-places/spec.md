# Feature Specification: Ein Board, zwei Orte

**Feature Branch**: `010-one-board-two-places`

**Created**: 2026-10-21

**Status**: Draft (nicht geplant)

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

## Requirements *(mandatory)*

Noch nicht ausgearbeitet. Wird bei `/speckit-clarify` und `/speckit-plan` ergänzt. Offene Punkte für die Klärung:

- Wie kommt die gebaute UI in die vendorte Engine (Größe, Upgrade über das Lock, Build-Schritt im Kit)?
- Liefert der lokale Modus auch Events für die Lauf-Ansicht (`/events.json`), oder nur das Board-Dokument?
- Ist der Import Teil des Kerns oder ein Plugin für ImmoAgent?
- Ändert sich mit dem Plugin-Mechanismus der Contract `plugins` in `sak.config/1` (heute `maxItems: 0`)?
- Soll das alte ImmoAgent-Board nach dem Import abgeschaltet werden, oder bleibt es bis zur Rückmigration?

## Success Criteria *(mandatory)*

- **SC-001**: Lokales und Online-Board sind bei gleichem Board-Dokument visuell gleich (Screenshot-Vergleich der Projektansicht).
- **SC-002**: Für ImmoAgent zeigt das Kit nach Import und mit Plugin dieselben Läufe und Blocker wie das alte Board. Jede verbleibende Kennzahl-Abweichung ist durch einen Tooltip oder Hinweis erklärt.
- **SC-003**: Jeder Ticker-Eintrag hat per Hover oder Fokus einen Hash und eine Zeit.

## Assumptions

- Das alte ImmoAgent-Board und die alte Pipeline bleiben während des Trials unverändert in Betrieb.
- Commit-Betreffe gelten als Metadaten (Constitution II). Teilen bleibt eine Entscheidung je Projekt.
