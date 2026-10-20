# Feature Specification: Contracts v1 – Event-, Board- und Ingest-Vertrag

**Feature Branch**: `002-contracts-v1`

**Created**: 2026-10-20

**Status**: Implemented

**Input**: ADR 0001 E1, E2 und Spec 001. Gesucht sind sprachneutrale, versionierte Verträge zwischen Engine/Collector (Python, im Zielprojekt) und Dashboard (TypeScript, VPS).

## Clarifications

### Session 2026-10-20

- Die Entscheidungen leiten sich aus ADR 0001 und Constitution I/II ab. Es gibt keine offenen Fragen an den Betreiber.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Ein Vertrag, zwei Sprachen (Priority: P1)

Engine und Dashboard validieren dieselben Daten mit denselben Regeln, obwohl sie in verschiedenen Sprachen geschrieben sind.

**Independent Test**: Ein Satz Beispieldateien (gültig und ungültig) wird von der Python-Validierung und von der TS-Validierung identisch beurteilt.

**Acceptance Scenarios**:

1. **Given** ein Event mit einem unbekannten Feld, **When** es geprüft wird, **Then** lehnen beide Seiten ab.
2. **Given** das Schema bekommt einen neuen Enum-Wert, **When** die Generierung läuft, **Then** kennen ihn TS-Typen und Python-Kopie ohne Handarbeit, und ein Test bricht ab, solange er im Vokabular fehlt.

### User Story 2 – Events kommen genau einmal an (Priority: P1)

Ein Projekt sendet Events mehrfach, etwa nach einem Netzwerkfehler. Das Dashboard zählt jedes Event nur einmal.

**Independent Test**: Dieselbe Event-ID zweimal einliefern ergibt genau einen gespeicherten Datensatz und die Meldung „duplicate“.

**Acceptance Scenarios**:

1. **Given** Event X wurde angenommen, **When** X erneut kommt, **Then** lautet die Antwort `duplicates: 1`, und nichts ändert sich.

### User Story 3 – Board-Dokument beschreibt den Projektstand vollständig (Priority: P1)

Das zentrale Dashboard zeigt Portfolio, Projekt-Board und Betreiber-Liste allein aus dem zuletzt gepushten Board-Dokument und den Events, ohne Zugriff auf das Repo.

**Independent Test**: Ein Board-Dokument aus einem ImmoAgent-ähnlichen Fixture enthält Specs mit Station, Fortschritt, Aufmerksamkeitseinträge, Läufe mit Stationen und Urteilen, Marker und Kennzahlen.

### User Story 4 – Versionen bleiben beherrschbar (Priority: P2)

Der Betreiber weiß, in welcher Reihenfolge er Dashboard und Projekte aktualisieren muss.

**Acceptance Scenarios**:

1. **Given** ein Projekt sendet `sak.event/2`, das Dashboard kennt nur `/1`, **When** es einliefert, **Then** wird mit einem klaren Versionsfehler abgelehnt, und das Projekt behält die Events in seiner Outbox.

### Edge Cases

- **Zu großes Event oder zu großer Batch:** Ablehnung mit Grund. Bei Einzel-Events wird nur das betroffene Event abgelehnt.
- **Zeitstempel ohne Zeitzone:** ungültig.
- **Board-Dokument eines anderen Projekts als das des Schlüssels:** Ablehnung (Spec 007).
- **Leeres Projekt ohne Specs:** gültiges Board-Dokument mit leeren Listen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Die Verträge MÜSSEN als JSON Schema (Draft 2020-12) unter `packages/contracts/schema/` liegen und sind dort die einzige Quelle.
  - `vocabulary.json`: die Ebenen und Werte aus Spec 001
  - `labels/de.json`
  - `event.schema.json`
  - `board.schema.json`
  - `ingest.schema.json`
- **FR-002**: Alle Enum-Werte in den Schemas MÜSSEN mit `vocabulary.json` übereinstimmen. Ein automatischer Test prüft das. Zu jedem Vokabular-Wert MUSS ein Label in `labels/de.json` existieren.
- **FR-003**: Aus den Schemas MÜSSEN Zod-Schemas und TS-Typen generiert werden (Paket `@sak/contracts`). Die Engine MUSS eine byte-gleiche Kopie der Schema-Dateien enthalten. Ein Test prüft die Gleichheit.
- **FR-004**: **Event-Hülle**, Kennung `"schema": "sak.event/1"`:

  | Feld | Pflicht | Regel |
  |---|---|---|
  | `schema` | ja | konstant `sak.event/1` |
  | `event_id` | ja | ULID (26 Zeichen, Crockford Base32), global eindeutig |
  | `type` | ja | Ereignisart aus dem Vokabular (Spec 001 FR-022) oder `diag.hook` |
  | `ts` | ja | RFC 3339 mit Zeitzone |
  | `project` | ja | Projektschlüssel (Spec 001 FR-004) |
  | `run_id` | nein | Lauf-ID (Spec 001 FR-009); Pflicht bei allen `run.*`, `round.*`, `station.*`, `verdict.*` |
  | `spec` | nein | `NNN-slug` |
  | `origin` | nein | `{machine?, worktree?, branch?, source?: local\|cloud}`, jeweils ≤ 100 Zeichen |
  | `data` | ja | Objekt, Form je `type` (FR-005) |

  Zusätzliche Felder sind unzulässig (`additionalProperties: false`, auch in `data`). Ein Event ist serialisiert ≤ 8 KB groß.
- **FR-005**: `data` je `type`. Freitext `reason` ist auf ≤ 500 Zeichen begrenzt.

  | type | data |
  |---|---|
  | `run.started` | `kind` (run_kind), `base_branch`, `base_commit` (40 hex), `max_rounds` |
  | `round.started` | `round` |
  | `station.started` | `round`, `role`, `agent`, `model?`, `effort?` |
  | `station.finished` | `round`, `role`, `agent`, `duration_s` (≥ 0) |
  | `verdict.recorded` | `round`, `role`, `verdict`, `must_count`, `may_count` |
  | `run.escalated` | `round`, `gate?`, `reason` |
  | `run.released`, `run.returned`, `run.paused`, `run.aborted` | `reason?` |
  | `run.resumed`, `run.approved`, `run.reviewed` | `{}` |
  | `run.merged` | `merge_commit?` (40 hex) |
  | `run.taken_over` | `reason`, `previous_state` |
  | `diag.hook` | `phase` (`start`\|`stop`), `keys` (Liste ≤ 50 Strings) |

- **FR-006**: **Board-Dokument**, Kennung `"schema": "sak.board/1"`. Pflichtfelder:
  - `generated_at`
  - `source` (`live`\|`snapshot`)
  - `kit_version`
  - `project` mit `{key, name, base_branch}`
  - `metrics` mit `{in_progress, done, blocked, waiting, mean_lead_time_days\|null}`
  - `specs[]`
  - `attention[]`
  - `runs[]`
  - `markers[]`
  - `ticker[]`
  - `notes[]`

  Felder der Listen-Einträge, je nach Liste:
  - `specs[]`:
    - `number`, `dir`, `title`
    - `stage` (Station oder `null`)
    - `descoped`, `blocked`
    - `waiting` (`approval`\|`clarification`\|`null`)
    - `tasks{done,open}`
    - `started_at?`, `finished_at?`, `updated_at?`
    - `lead_time_days?`
  - `attention[]`: `kind`, `spec?`, `reason`, `source`
  - `runs[]`:
    - `run_id`, `spec`, `kind`, `state`
    - `round`, `max_rounds`
    - `active`
    - `started_at`, `updated_at`, `last_event_at`
    - `idle`, `stale`
    - `origin?`
    - `stations[]`, darin `{round, role, agent, model?, state, started_at, duration_s?, verdict?, must_count?, may_count?}`
    - `escalations[]`, darin `{ts, round, gate?, reason, open}`
    - höchstens 20 Läufe, neueste zuerst
  - `markers[]`: `{kind: deploy|verified, specs[], ts, commit}`
  - `ticker[]`:
    - `{ts, spec?, kind: commit|deploy|verified, text?}`
    - höchstens 30 Einträge
    - `text` (Commit-Betreff) nur, wenn das Projekt es per Config erlaubt (Spec 004)
  - `notes[]`: Hinweise wie „Datei X nicht lesbar“, ≤ 20 Einträge

  Gesamtgröße ≤ 512 KB.
- **FR-007**: **Ingest-Anfrage** `sak.ingest/1`:
  - Inhalt: `{schema, project, sent_at, events[] (≤ 500), board?}`
  - Antwort `sak.ingest_result/1`: `{accepted, duplicates, rejected[{event_id?, error}], board_accepted}`
  - Request ≤ 2 MB.
- **FR-008**: **Versionsregeln:**
  - Innerhalb von `/1` sind nur rückwärtskompatible Erweiterungen erlaubt: neue optionale Felder, neue Enum-Werte, neue Event-Typen.
  - Alles andere bekommt eine neue Hauptversion.
  - Ein Empfänger lehnt unbekannte Hauptversionen und unbekannte Werte ab.
  - **Betriebsregel:** Das Dashboard wird vor den Projekten aktualisiert.
- **FR-009**: Das Paket `@sak/contracts` MUSS die Deep-Link-Helfer für die Dashboard-URLs enthalten:
  - `#/portfolio`
  - `#/project/:key`
  - `#/project/:key?tab=board|runs|attention|conflicts`
  - `#/run/:key/:runId`

  Dazu einen Parser, der unbekannte Tabs auf `board` zurückführt. Projektschlüssel und Lauf-ID werden beim Bauen und Parsen validiert.
- **FR-010**: Unter `packages/contracts/examples/` MÜSSEN gültige und ungültige Beispieldateien je Schema liegen. Beide Sprachen testen dagegen. Dazu kommt ein Board-Beispiel, das der ImmoAgent-Pilotsituation entspricht: Lauf 066 gemergt, 084 pausiert, 088 eskaliert, Specs in allen Stationen.
- **FR-011**: Die Gerüst-Artefakte `examples/event-payloads/stage-changed.json` und `apps/dashboard-web/src/lib/routes.ts` sowie das alte `EventEnvelope` in `packages/contracts/src/index.ts` MÜSSEN entfernt oder ersetzt werden.

### Key Entities

Event, Board-Dokument, Ingest-Anfrage, Vokabular, Label-Satz (siehe FR-004 bis FR-007, Spec 001).

## Success Criteria *(mandatory)*

- **SC-001**: 100 % der Beispieldateien werden von Python und TS gleich beurteilt.
- **SC-002**: Ein neuer Enum-Wert erfordert Änderungen an genau zwei Stellen: Schema und Vokabular mit Label. Alles andere wird generiert oder per Test erzwungen.
- **SC-003**: Das ImmoAgent-Pilot-Board ist ohne Informationsverlust gegenüber dem 092-Board-Dokument im Format `sak.board/1` darstellbar. Ausgenommen sind die bewusst entfallenen Spec-Status (Spec 001, Anhang A).

## Assumptions

- ULIDs werden in Python selbst erzeugt (Zeit + Zufall, Standardbibliothek). Eine externe Abhängigkeit braucht es dafür nicht.
- Für die Zod-Generierung wird ein etabliertes Werkzeug genutzt, etwa `json-schema-to-zod`. Das generierte Ergebnis wird eingecheckt, damit Builds reproduzierbar sind.
