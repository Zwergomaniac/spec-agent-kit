# Dashboard-Konzept v1

Stand: umgesetzt in Spec 007. Die Deep-Link-Helfer stehen in `packages/contracts/src/deep-links.ts`, der Router der UI in `apps/dashboard-web/src/router.ts`.

## Startansicht

Die Standardansicht ist `Portfolio`. Ein leerer, unbekannter oder ungültiger Hash ergibt ebenfalls das Portfolio.

## Ansichten

- **Portfolio:** Projektkarten mit Warnungen; ein eskalierter Lauf ist hervorgehoben.
- **Projekt:** Kennzahlen, Stationsspalten, Spalte „Mensch prüft / entscheidet“, Agenten-Panel, Ticker, zwei Diagramme. Vier Tabs.
- **Lauf:** Runden, Stationen, Urteile, Eskalationen, Event-Log.
- **Admin:** Projekte anlegen, Schlüssel erneuern, Projekte entfernen. Der Schlüssel erscheint genau einmal.
- **Login:** Anmeldung mit dem Admin-Passwort.

## URL-Modell

Hash-Router. Jede Ansicht ist direkt verlinkbar.

| URL | Ansicht |
|---|---|
| `#/portfolio` | Portfolio |
| `#/project/:projectKey` | Projekt, Tab `board` (Default) |
| `#/project/:projectKey?tab=board` | Projekt, Tab Board |
| `#/project/:projectKey?tab=runs` | Projekt, Tab Läufe |
| `#/project/:projectKey?tab=attention` | Projekt, Tab „Mensch prüft“ |
| `#/project/:projectKey?tab=conflicts` | Projekt, Tab Konflikte |
| `#/run/:projectKey/:runId` | Lauf-Ansicht |
| `#/admin` | Projektverwaltung |
| `#/login` und `#/login?next=<hash>` | Anmeldung |

Regeln:

- Gültige Tabs sind `board`, `runs`, `attention` und `conflicts`. Ein unbekannter Tab wird zu `board`. Der frühere Tab `operator` entfällt; seine Aufgabe übernimmt `attention`.
- `conflicts` zeigt in v1 nur einen Hinweis. Konfliktdaten gibt es erst mit dem Parallelbetrieb (siehe [follow-ups](../follow-ups.md)).
- Projektschlüssel und Lauf-ID werden gegen die Contracts-Schemas geprüft; ungültige Werte führen zum Portfolio.
- `#/admin` und `#/login` sind UI-Routen und gehören nicht zu den Contracts-Deep-Links.

## Anmeldung und Rücksprung

Fehlt die Session, erscheint die Anmeldung unter der angefragten URL. Der Hash bleibt unverändert, nach dem Login rendert dieselbe Route (Rücksprung). Zusätzlich wird `#/login?next=<hash>` unterstützt; erlaubt sind nur interne Ziele (`#/…`, nicht `#/login`). Wer angemeldet auf `#/login` landet, wird zum Rücksprungziel oder zum Portfolio geleitet.

## Aktualisierung und Darstellung

- Polling alle 10 s, nur bei sichtbarem Tab; „zuletzt aktualisiert“ wird angezeigt.
- Fehler- und Leerzustände sind ausgeführt.
- Alle Vokabularwerte laufen über die Labels aus `packages/contracts` (Locale `de`). Unbekannte Werte erscheinen als „unbekannt (wert)“.
- Dark Mode.
