# Feature Specification: Dashboard v1

**Feature Branch**: `007-dashboard-v1`

**Created**: 2026-10-20

**Status**: Implemented

**Input**: ADR 0001 E10, Constitution II/IV, `docs/architecture-vision.md`, `docs/ui/dashboard-concept.md`. Die Board-Darstellung aus ImmoAgent 092 (Spalten je Station plus „Mensch prüft“, Kacheln, Agenten-Panel, Ticker) hat sich bewährt.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Portfolio auf einen Blick (Priority: P1)

Nach der Anmeldung sieht der Betreiber alle Projekte. Je Projekt sieht er:
- den aktiven Lauf mit Spec, Zustand, Runde und aktueller Station
- die Zahl der offenen Aufmerksamkeitseinträge
- Specs in Arbeit
- die letzte Aktivität
- Warnungen für inaktive oder verwaiste Läufe und für Projekte ohne Push seit mehr als 24 h

**Independent Test**: Mit zwei eingelieferten Projekten zeigt `#/portfolio` zwei Karten mit korrekten Werten.

**Acceptance Scenarios**:

1. **Given** Projekt A hat einen eskalierten Lauf, **When** das Portfolio lädt, **Then** ist A hervorgehoben, mit Eskalationsgrund und Link `#/run/a/<runId>`.
2. **Given** ein nicht angemeldeter Aufruf von `#/project/a`, **When** die Seite lädt, **Then** erscheint die Anmeldung. Nach dem Login landet der Betreiber direkt auf `#/project/a`.

### User Story 2 – Projekt-Board mit Deep Links (Priority: P1)

`#/project/:key` zeigt Tabs, jeder direkt verlinkbar (`?tab=`):
- **board:** Spalten je Station plus Spalte „Mensch prüft / entscheidet“, Kacheln für die Kennzahlen, Agenten-Panel für den aktiven Lauf, Ticker
- **runs:** Laufliste
- **attention:** Liste mit Art, Grund und Quelle
- **conflicts:** in v1 ein ehrlicher Hinweis, dass dies erst mit dem Parallelbetrieb kommt

**Acceptance Scenarios**:

1. **Given** `#/project/a?tab=runs` in einem neuen Browser-Tab, **When** es geöffnet wird, **Then** ist der Tab „Läufe“ aktiv.
2. **Given** ein unbekannter Tab `?tab=foo`, **When** geöffnet, **Then** wird `board` gezeigt.

### User Story 3 – Lauf-Ansicht (Priority: P1)

`#/run/:key/:runId` zeigt den Verlauf eines Laufs:
- Runden mit ihren Stationen: Rolle, Agent, Modell, Dauer, Urteil, Muss- und Kann-Zahl
- Eskalationen
- Zustandsverlauf aus den Events
- Event-Log nur mit Metadaten

### User Story 4 – Projekte liefern sicher ein (Priority: P1)

Ein Projekt liefert Events und Board per `POST /api/ingest` mit seinem Projekt-Schlüssel. Ungültiges, Fremdes und Übergroßes wird abgelehnt. Duplikate werden erkannt.

**Acceptance Scenarios**:

1. **Given** der Schlüssel von Projekt A, **When** ein Event mit `project: b` kommt, **Then** wird das Event mit „project mismatch“ abgelehnt.
2. **Given** kein oder ein falscher Schlüssel, **When** eingeliefert wird, **Then** folgt 401, und nichts wird gespeichert.
3. **Given** ein Request größer als 2 MB, **When** er eingeliefert wird, **Then** folgt 413.

### User Story 5 – Projektverwaltung (Priority: P2)

Der Admin legt Projekte an (Schlüssel, Name), sieht jeden Projekt-Schlüssel genau einmal, kann den Schlüssel erneuern und Projekte entfernen. Das geht über die UI (`#/admin`) und als CLI im Container.

### Edge Cases

- **Projekt ohne Board-Dokument:** Karte mit „noch keine Daten“.
- **Board-Version neuer als bekannt:** Ablehnung beim Ingest (Spec 002 FR-008).
- **SQLite-Datei fehlt beim Start:** wird angelegt, die Migration läuft.
- **Viele Events:** Ältere als 30 Tage werden täglich gelöscht. Boards bleiben.
- **Zu viele Login-Versuche:** Sperre pro IP für 15 min nach 5 Fehlversuchen.

## Requirements *(mandatory)*

### Functional Requirements

**Betrieb**

- **FR-001**: Das Dashboard MUSS als ein Container laufen. Ein Node-Prozess liefert API und gebaute UI aus, auf Port 3000. Die SQLite-Datei liegt unter `/data` (WAL).
  - Konfiguration nur über Umgebungsvariablen: `SAK_ADMIN_PASSWORD_HASH`, `SAK_SESSION_SECRET`, `SAK_DB_PATH` (`/data/dashboard.db`), `SAK_RETENTION_DAYS` (30), `SAK_TRUST_PROXY` (true).
  - Fehlen Pflicht-Secrets, verweigert der Start mit einer klaren Meldung.
- **FR-002**: `deploy/dashboard/` MUSS enthalten:
  - Multi-Stage-`Dockerfile`, non-root
  - `compose.snippet.yml` mit externem Netz für edge-caddy (Name per Variable), Volume und Healthcheck
  - `caddy.example` als Beispiel-Block, nur als Doku, da Caddy nicht von diesem Repo verwaltet wird

**Auth**

- **FR-003**: Lesen und Admin-Aktionen MÜSSEN eine Anmeldung erfordern:
  - Ein Admin-Passwort, gespeichert als scrypt-Hash in der Umgebung.
  - Signiertes Session-Cookie: HttpOnly, Secure, SameSite=Strict, 12 h gültig.
  - Login-Sperre gemäß Edge Case.
  - Ein Hilfsbefehl erzeugt den Hash.
- **FR-004**: Ingest MUSS per `Authorization: Bearer <projekt-schlüssel>` authentifiziert sein.
  - Schlüssel: 256 Bit zufällig, gespeichert als SHA-256.
  - Vergleich in konstanter Zeit.
  - Rate-Limit 60 Requests pro Minute und Projekt.

**API**

- **FR-005**: Endpunkte. Alle außer `healthz`, `login` und `ingest` brauchen eine Session.
  - `GET /healthz`
  - `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`
  - `POST /api/ingest` (Spec 002 FR-007)
  - `GET /api/meta`: Kit-Version, Vokabular, Labels
  - `GET /api/portfolio`
  - `GET /api/projects/:key`: Board-Dokument und Ingest-Status
  - `GET /api/projects/:key/runs/:runId`: Lauf aus dem Board plus dessen Events
  - `GET /api/projects/:key/events?run=&since=&limit=` (≤ 500)
  - `GET|POST /api/admin/projects`, `POST /api/admin/projects/:key/rotate`, `DELETE /api/admin/projects/:key`
- **FR-006**: Ingest MUSS jedes Event einzeln mit den Contracts validieren. Duplikate erkennt es an der `event_id`. Fremde Projekte lehnt es ab. Das Board wird übernommen, wenn es gültig ist, zum Projekt passt und `generated_at` neuer ist als das gespeicherte. Die Antwort folgt Spec 002 FR-007.
- **FR-007**: Gespeichert werden nur die validierten Contract-Daten (Constitution II). Request-Bodies werden nicht geloggt.

**UI**

- **FR-008**: Die UI MUSS Hash-Routing mit den Deep Links aus Spec 002 FR-009 nutzen. Startansicht ist `#/portfolio`. Dazu kommen `#/login` und `#/admin`.
- **FR-009**: Die UI MUSS alle Werte über die Labels aus `@sak/contracts` anzeigen, im Locale `de`. Unbekannte Werte erscheinen als „unbekannt (wert)“.
- **FR-010**: Die Ansichten aktualisieren sich alle 10 s, solange der Tab sichtbar ist. Der Zeitpunkt der letzten Aktualisierung wird angezeigt.
- **FR-011**: Die UI MUSS mit Tastatur bedienbar sein, Dark Mode haben (System plus Umschalter) und ab 360 px Breite nutzbar sein. Unter 900 px werden die Board-Spalten untereinander dargestellt.
- **FR-012**: Diagramme gibt es in v1 höchstens zwei, beide im Projekt-Board: Durchlaufzeit je Spec und Urteile je Runde. Weitere Diagramme sind nicht vorgesehen.

### Key Entities

Projekt (Schlüssel, Name, Schlüssel-Hash, letzte Einlieferung), Event (gespeichert), Board (letztes je Projekt), Admin-Session.

## Success Criteria *(mandatory)*

- **SC-001**: Jede der Deep-Link-Formen öffnet in einem frischen Tab nach dem Login direkt die richtige Ansicht (E2E-Test).
- **SC-002**: Ingest-Vertragstests decken ab: 401, 413, Fremdprojekt, Duplikat, ungültiges Event (400 pro Event, Rest angenommen), veraltetes Board.
- **SC-003**: Der Container startet mit leerem Volume in unter 5 s und braucht im Leerlauf unter 150 MB RAM.
- **SC-004**: Das Pilot-Board aus `packages/contracts/examples/` wird vollständig dargestellt (visueller Smoke-Test mit Screenshot).

## Assumptions

- Ein Admin-Konto reicht (ADR E10). Mehrere Benutzer und Rollen sind nicht vorgesehen.
- TLS terminiert edge-caddy. Das Cookie-Flag `Secure` lässt sich für die lokale Entwicklung per `NODE_ENV=development` abschalten.
