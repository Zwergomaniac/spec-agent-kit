# Feature Specification: Domänenmodell und Status-Begriffe

**Feature Branch**: `001-domain-model-vocabulary`

**Created**: 2026-10-20

**Status**: Draft

**Input**: Beschreibung des Betreibers: „Ein gemeinsames Domänenmodell und Statusvokabular für Spec-Agent-Kit. Spec-Stationen, Lauf-Zustände und Urteile sind getrennte Ebenen. Maschinenwerte sind englisch, Labels per Locale (Default de). ImmoAgent wird per Zuordnungstabelle abgebildet. Der Weg zu parallelen Läufen bleibt offen.“ Grundlage: ADR 0001 (E1, E4, E8, E9), ImmoAgent Specs 092 und 093.

## Kontext

Heute vermischen Gerüst und Referenz Begriffe aus drei Ebenen:
- Das Gerüst nutzt `stage: review|ui_review|operator_wait` und `status: needs_changes`.
- ImmoAgent nutzt deutsche Stationen (`klaerung`, `umsetzung_fertig`), englische Lauf-Zustände (`building`, `escalated`) und deutsche Urteile (`Änderung`, `Mensch prüft`).

Ohne gemeinsame Begriffe driften Engine, Collector und Dashboard sofort auseinander. Diese Spec legt **nur die Begriffe, ihre Bedeutung und ihre erlaubten Übergänge** fest. Datenformate (Schema, Event-Hülle, Board-Dokument) regelt Spec 002, die Konfiguration Spec 004.

## Clarifications

### Session 2026-10-20

- Q: Belegt ein `paused`-Lauf die Projekt-Sperre? → A: Nein. Pause gibt die Sperre frei, Fortsetzen nur bei freier Sperre, mehrere pausierte Läufe erlaubt (FR-013).
- Q: Wird Arbeit der Hauptsitzung außerhalb der Pipeline modelliert? → A: In v1 nicht. Die Lauf-Art `manual` ist reserviert, das Feld Lauf-Art existiert ab v1 (FR-025).

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Betreiber liest überall dieselben Begriffe (Priority: P1)

Der Betreiber sieht einen Lauf im lokalen Board, im zentralen Dashboard und im Abschlussbericht des Orchestrators. Überall stehen derselbe Zustand, dieselbe Station und dasselbe Urteil, mit denselben deutschen Bezeichnungen.

**Why this priority**: Ein uneinheitliches Vokabular ist das Hauptrisiko aus dem Audit (D2). Jede weitere Spec baut darauf auf.

**Independent Test**: Für jeden Begriff im Vokabular existieren genau ein Maschinenwert, eine Definition und eine deutsche Bezeichnung. Ein Prüfer kann für jeden Wert, der in den Specs 002 bis 007 vorkommt, den Eintrag im Vokabular finden.

**Acceptance Scenarios**:

1. **Given** ein Lauf im Zustand `escalated`, **When** Board, Dashboard und Bericht ihn anzeigen, **Then** steht überall die Bezeichnung „Eskaliert“, und der Maschinenwert ist `escalated`.
2. **Given** ein neuer Begriff wird in einer späteren Spec gebraucht, **When** er nicht im Vokabular steht, **Then** muss zuerst das Vokabular erweitert werden. Ein Wert außerhalb des Vokabulars gilt als Vertragsverletzung.

---

### User Story 2 – Drei Ebenen sind klar getrennt (Priority: P1)

Der Betreiber erkennt auf einen Blick drei Dinge: wo eine Spec im Lebenszyklus steht (Station), was gerade ein Agenten-Lauf tut (Lauf-Zustand) und was ein Prüfer entschieden hat (Urteil).

**Why this priority**: Das Gerüst vermischt alle drei. Das macht Filter, Kennzahlen und Deep Links unzuverlässig.

**Independent Test**: Jeder Wert gehört zu genau einer Ebene. Kein Wert kommt in zwei Ebenen vor.

**Acceptance Scenarios**:

1. **Given** eine Spec in Station `implementing` mit einem Lauf im Zustand `reviewing`, **When** beide Prüfer `changes_requested` urteilen, **Then** bleibt die Station `implementing`, der Lauf wechselt nach `building` (nächste Runde), und das Urteil ist am Durchgang gespeichert.
2. **Given** ein Lauf endet mit `merged`, **When** danach ein Deploy-Marker für die Spec erscheint, **Then** wechselt die Station auf `deployed`. Der Lauf bleibt `merged`.

---

### User Story 3 – Lauf-Historie bleibt erhalten, paralleler Betrieb wird nicht verbaut (Priority: P2)

Mehrere Läufe derselben Spec, zum Beispiel ein abgebrochener und ein neuer, sind einzeln adressierbar und verlinkbar. Ein späterer Parallelbetrieb über Worktrees braucht kein neues Modell.

**Why this priority**: In ImmoAgent überschreibt `run.json` die Historie. Deep Links auf `#/run/:project/:runId` brauchen eine stabile Lauf-ID.

**Independent Test**: Zwei Läufe derselben Spec haben unterschiedliche IDs. Beide sind mit ihren Zuständen und Urteilen abrufbar.

**Acceptance Scenarios**:

1. **Given** Lauf A der Spec 012 wurde `aborted`, **When** Lauf B für Spec 012 startet, **Then** hat B eine neue Lauf-ID, und A bleibt mit Zustand `aborted` erhalten.
2. **Given** v1 erlaubt höchstens einen aktiven Lauf je Projekt, **When** später zwei Worktrees parallel laufen, **Then** unterscheiden sich ihre Läufe schon durch Lauf-ID und Herkunft. Das Modell muss dafür nicht geändert werden, nur die Sperrregel.

---

### User Story 4 – Betreiber sieht, was auf ihn wartet (Priority: P2)

Alles, was eine menschliche Entscheidung braucht, erscheint als Eintrag mit fester Art: Eskalation, Freigabe, Klärung, Blocker, Entscheidung, Betreiber-Aufgabe oder hängender Lauf.

**Why this priority**: Die Spalte „Mensch prüft / entscheidet“ in ImmoAgent hat sich bewährt. Sie ist der Kern der Betreiber-Ansicht (`?tab=operator`).

**Independent Test**: Für jede Art ist festgelegt, wodurch sie entsteht und wodurch sie verschwindet.

**Acceptance Scenarios**:

1. **Given** eine Spec hat alle Tasks und es gibt noch kein „umsetzen“, **When** das Board berechnet wird, **Then** erscheint ein Eintrag der Art `approval`.
2. **Given** ein Lauf ist `escalated`, **When** der Betreiber ihn freigibt (`released`), **Then** verschwindet der `escalation`-Eintrag.

---

### User Story 5 – ImmoAgent ist verlustfrei abbildbar (Priority: P3)

Jeder Status-, Stations-, Urteils- und Ereigniswert aus ImmoAgent hat eine eindeutige Entsprechung im Vokabular. Die spätere Rückmigration ist damit eine reine Umbenennung.

**Why this priority**: ADR 0001 E11 sieht eine Rückmigration vor. Für v1 ist sie nicht nötig.

**Independent Test**: Die Zuordnungstabelle deckt alle Werte aus den ImmoAgent-Verträgen `events-format.md`, `verdict-format.md`, 092 `data-model.md` und `feature_status.py` ab.

**Acceptance Scenarios**:

1. **Given** ein ImmoAgent-Ereignis `{"kind":"verdict","verdict":"Mensch prüft"}`, **When** es per Tabelle übersetzt wird, **Then** ergibt sich `verdict.recorded` mit Urteil `needs_human`.

### Edge Cases

- **Spec ohne Tasks:** Die Station ist höchstens `planned`, der Fortschritt `0/0`. Die Spec hat keinen `approval`-Eintrag, denn es gibt keine Tasks, die freigegeben werden könnten.
- **Zurückgestellte Spec (`descoped`):** Sie hat keine Station, zählt nicht als „in Arbeit“ und erzeugt keine Aufmerksamkeitseinträge.
- **Deploy-Marker vor dem letzten Task-Commit:** Er zählt nicht. Die Station bleibt `implemented`. Diese Regel stammt aus ImmoAgent.
- **Projekt ohne Deploy:** Die Stationen `deployed` und `verified` sind je Projekt abschaltbar. `implemented` ist dann die Endstation. Die Regelung dazu trifft Spec 004.
- **Lauf ohne Ereignis seit langer Zeit:** Er bekommt keinen neuen Zustand. „Inaktiv“ und „verwaist“ werden berechnet, siehe FR-012.
- **Ungültiges Prüfer-Urteil:** Es wird nicht als Urteil gespeichert. Nach einem erneuten Versuch gilt es als `needs_human` mit Grund „Urteil ungültig“.
- **Unbekannter Wert von außen** (anderer Kit-Stand): Er wird nicht verworfen. Er wird als „unbekannt“ angezeigt und als Hinweis gemeldet. Das Verhalten dazu regelt Spec 002.

## Requirements *(mandatory)*

### Functional Requirements

**Allgemein**

- **FR-001**: Das Vokabular MUSS für jeden Begriff festlegen: Maschinenwert (englisch, `lower_snake_case`, nur ASCII), Ebene, Definition und deutsche Bezeichnung (Locale `de`). Weitere Locales MÜSSEN ergänzbar sein, ohne Maschinenwerte zu ändern.
- **FR-002**: Jeder Maschinenwert MUSS genau einer Ebene angehören. Die Ebenen sind: Spec-Station, Lauf-Zustand, Urteil, Befund-Schwere, Aufmerksamkeitsart, Ereignisart, Rolle.
- **FR-003**: Maschinenwerte DÜRFEN nach Freigabe des Vokabulars v1 nicht umbenannt werden. Neue Werte sind erlaubt. Entfernen nur mit neuer Hauptversion (siehe Spec 002).

**Projekt**

- **FR-004**: Ein Projekt MUSS einen Projektschlüssel haben: 2 bis 40 Zeichen, Kleinbuchstaben, Ziffern und Bindestrich, beginnend mit einem Buchstaben, ohne Bindestrich am Ende, zum Beispiel `ai-forge`. Der Schlüssel ist dauerhaft und erscheint in URLs, Events und Pfaden.

**Spec und Spec-Station**

- **FR-005**: Eine Spec MUSS durch ihr Verzeichnis `NNN-slug` identifiziert sein. Ihre Nummer `NNN` ist innerhalb des Projekts eindeutig.
- **FR-006**: Die Spec-Station MUSS genau einer der folgenden Werte sein, in fester Reihenfolge. Die höchste zutreffende Bedingung gewinnt:

  | Wert | DE | Bedingung |
  |---|---|---|
  | `specified` | Spec | Spec-Dokument existiert |
  | `clarified` | Klärung | Spec enthält einen Klärungsabschnitt |
  | `planned` | Plan | Plan existiert |
  | `tasked` | Tasks | Taskliste existiert |
  | `implementing` | Umsetzung | ≥ 1 Task erledigt |
  | `implemented` | Umsetzung fertig | alle Tasks erledigt, ≥ 1 Task |
  | `deployed` | Deploy | Deploy-Marker nach dem letzten Task-Commit |
  | `verified` | Live geprüft | Verified-Marker |

- **FR-007**: Eine Spec MUSS zusätzlich führen: Task-Fortschritt (erledigt, offen), `descoped` (ja/nein), `blocked` (ja/nein) und einen Wartegrund (`approval`, `clarification` oder keiner). Eine Spec mit `descoped` hat keine Station.
- **FR-008**: Deploy- und Verified-Marker MÜSSEN als Commit-Marker erkennbar sein: `deploy(NNN): …` und `verified(NNN): …`. Listen und Bereiche wie `deploy(084,085)` und `verified(079-082)` sind erlaubt.

**Lauf und Lauf-Zustand**

- **FR-009**: Ein Lauf ist ein Durchgang der Agenten-Pipeline für genau eine Spec. Er MUSS eine Lauf-ID haben, die im Projekt eindeutig und URL-tauglich ist: `NNN-YYYYMMDD-HHMMSS` (Spec-Nummer plus Startzeit in UTC), zum Beispiel `012-20261020-140311`. Ein neuer Lauf MUSS eine neue ID bekommen. Frühere Läufe bleiben erhalten.
- **FR-010**: Der Lauf-Zustand MUSS einer der folgenden Werte sein:

  | Wert | DE | Art | Bedeutung |
  |---|---|---|---|
  | `building` | Baut | aktiv | Builder arbeitet (Runde n) |
  | `reviewing` | Wird geprüft | aktiv | Prüfer arbeiten |
  | `approved` | Freigegeben | aktiv | Alle Urteile `approve` oder vom Betreiber freigegeben; wartet auf Merge |
  | `escalated` | Eskaliert | aktiv | Wartet auf Entscheidung des Betreibers |
  | `paused` | Pausiert | ruhend | Bewusst unterbrochen, fortsetzbar |
  | `merged` | Gemergt | Ende | In den Basis-Branch gemergt |
  | `reviewed` | Geprüft | Ende | Nur-Prüfung-Lauf abgeschlossen, ohne Merge |
  | `aborted` | Abgebrochen | Ende | Verworfen; Branch bleibt bestehen |

- **FR-011**: Nur diese Übergänge sind erlaubt:
  - `building → reviewing | escalated | paused | aborted`
  - `reviewing → building` (nächste Runde, nur wenn Runde < Rundenlimit) `| approved | escalated | reviewed | paused | aborted`
  - `approved → merged | escalated | aborted`
  - `escalated → approved | building` (Betreiber gibt mit Auftrag zurück) `| paused | aborted`
  - `paused → building | reviewing` (Fortsetzen an der unterbrochenen Station) `| aborted`

  Endzustände haben keine Übergänge. Jeder Übergang MUSS als Ereignis protokolliert werden.
- **FR-012**: „Inaktiv“ und „verwaist“ sind KEINE Zustände. Sie MÜSSEN aus dem Zeitpunkt des letzten Ereignisses eines aktiven Laufs berechnet werden:
  - **inaktiv:** ab einer Anzeigeschwelle, Default 60 min
  - **verwaist:** ab einer Übernahmeschwelle, Default 6 h

  Ein verwaister Lauf DARF nur durch ausdrückliche Betreiberaktion beendet oder übernommen werden.
- **FR-013**: In v1 MUSS gelten: höchstens ein Lauf je Projekt in einem aktiven Zustand. Ein `paused`-Lauf belegt die Sperre nicht. Fortsetzen (`paused → building | reviewing`) ist nur erlaubt, wenn kein anderer Lauf des Projekts aktiv ist. Mehrere pausierte Läufe gleichzeitig sind erlaubt.
- **FR-014**: Ein Lauf MUSS eine Herkunft führen können. Pflicht ist der Basis-Branch, optional sind Maschine, Worktree und Quelle (`local` oder `cloud`). Die optionalen Felder sind für den Parallelbetrieb vorgesehen und in v1 nicht erforderlich.

**Station, Rolle, Runde**

- **FR-015**: Eine Pipeline-Station ist ein Schritt in einer Runde, der von genau einer Rolle ausgeführt wird. Für die Rollen MUSS es folgende Werte geben:

  | Wert | DE | Art | v1 |
  |---|---|---|---|
  | `builder` | Builder | baut | mitgeliefert |
  | `code_review` | Code-Prüfung | prüft | mitgeliefert |
  | `ui_review` | UI-Prüfung | prüft | mitgeliefert, abschaltbar |
  | `security_review` | Sicherheitsprüfung | prüft | vorgesehen, optional |
  | `docs` | Doku | baut | vorgesehen, optional |
  | `integrator` | Integration | führt zusammen | vorgesehen ab Parallelbetrieb |

  Welche Rollen ein Projekt nutzt und wie sie besetzt sind (Agent, Modell), regelt Spec 004.
- **FR-016**: Eine Runde MUSS aus einer Bau-Station und den aktiven Prüf-Stationen bestehen. Die Rundenzahl beginnt bei 1 und ist durch ein Projekt-Limit begrenzt, Default 2. Der Zustand einer Station ist `running` (DE „läuft“) oder `finished` („fertig“).

**Urteil und Befund**

- **FR-017**: Jede Prüf-Station MUSS genau ein Urteil liefern:

  | Wert | DE | Bedeutung |
  |---|---|---|
  | `approve` | OK | Keine Muss-Befunde |
  | `changes_requested` | Änderung | ≥ 1 Muss-Befund, vom Builder behebbar |
  | `needs_human` | Mensch prüft | Entscheidung oder Prüfung durch den Betreiber nötig |

- **FR-018**: Befunde MÜSSEN eine Schwere haben: `must` („Muss“) oder `may` („Kann“). Ein `approve` mit einem `must` gilt als `changes_requested`. Ein `changes_requested` ohne `must` ist ungültig.
- **FR-019**: Das Gesamturteil einer Runde MUSS das stärkste Einzelurteil sein, in der Rangfolge `approve < changes_requested < needs_human`. Daraus folgt:
  - `approve` → `approved`
  - `changes_requested` → nächste Runde, oder `escalated`, wenn das Rundenlimit erreicht ist
  - `needs_human` → `escalated`

**Gates und Eskalation**

- **FR-020**: Das Vokabular MUSS folgende Gate-Arten kennen:
  - `start_approval`: ausdrückliches „umsetzen“ des Betreibers je Spec vor dem Lauf
  - `protected_paths`: Änderung an geschützten Pfaden → Eskalation ohne Prüfung
  - `review_integrity`: Prüfer hat das Repo verändert → Eskalation
  - `round_limit`
  - `release`: Freigabe eines eskalierten Laufs
  - `deploy_approval`

  Jede Eskalation MUSS einen Grund und, wo möglich, ihre Gate-Art tragen.

**Betreiber-Aufmerksamkeit**

- **FR-021**: Einträge, die eine menschliche Entscheidung brauchen, MÜSSEN genau eine dieser Arten haben:

  | Wert | DE | Entsteht durch | Verschwindet durch |
  |---|---|---|---|
  | `escalation` | Eskaliert | Lauf in `escalated` | Release, Rückgabe oder Abbruch |
  | `approval` | Freigabe | Taskliste fertig, kein „umsetzen“ | Laufstart |
  | `clarification` | Klärung | offene Klärungsmarker in der Spec | Marker entfernt |
  | `blocker` | Blocker | gemeldeter Blocker (Plugin, z. B. Blocker-Datei) | Blocker aufgehoben |
  | `decision` | Entscheidung | offene Entscheidung (Plugin) | Entscheidung erfasst |
  | `operator_task` | Betreiber-Aufgabe | offene Task mit Betreiber-Kennzeichnung | Task erledigt |
  | `stale_run` | Lauf hängt | Lauf verwaist (FR-012) | Fortsetzen, Übernahme oder Abbruch |

  Jeder Eintrag MUSS Art, Spec (falls zutreffend), Grund und Quelle tragen.

**Ereignisse**

- **FR-022**: Das Vokabular MUSS folgende Ereignisarten kennen. Die Form der Ereignisse regelt Spec 002.
  - `run.started`
  - `round.started`
  - `station.started`
  - `station.finished`
  - `verdict.recorded`
  - `run.escalated`
  - `run.released`
  - `run.returned` (Rückgabe an den Builder)
  - `run.approved`
  - `run.paused`
  - `run.resumed`
  - `run.merged`
  - `run.reviewed`
  - `run.aborted`
  - `run.taken_over`

  Diagnose-Ereignisse MÜSSEN als solche erkennbar sein und dürfen keine Statuswirkung haben.
- **FR-023**: Ereignisse und alle hier definierten Begriffe tragen nur Metadaten. Code, Diffs, Prompts, Antworttexte und Secrets sind nie Teil davon (CLAUDE.md, Regel 4).

**Zuordnung zu ImmoAgent**

- **FR-024**: Die Spec MUSS eine vollständige Zuordnungstabelle von ImmoAgent-Werten auf das Vokabular enthalten (Anhang A). Werte ohne Entsprechung MÜSSEN als solche benannt werden.

**Ausgeschlossene Erfassung**

- **FR-025**: Ein Lauf MUSS eine Lauf-Art tragen. Die Werte sind `pipeline` (DE „Pipeline“, Default) und `review_only` (DE „Nur Prüfung“, endet mit `reviewed`). Der Wert `manual` (DE „Manuell“) für Arbeit der Hauptsitzung außerhalb der Pipeline (ImmoAgent 092 FR-018) ist reserviert, wird in v1 aber nicht erzeugt. Diese Arbeit ist in v1 nur über Commits, Ticker und Spec-Station sichtbar. Eine spätere Spec legt Zustände und Sperrverhalten für `manual` fest.

### Key Entities

- **Projekt**: ein Repo, das das Kit nutzt. Schlüssel (FR-004), Anzeigename, Basis-Branch. Hat viele Specs und Läufe.
- **Spec**: eine Feature-Spezifikation (`NNN-slug`). Station, Task-Fortschritt, descoped, blocked, Wartegrund. Hat 0..n Läufe.
- **Lauf**: ein Pipeline-Durchgang für eine Spec. Lauf-ID, Lauf-Art (FR-025), Zustand, aktuelle Runde, Basis-Commit, Herkunft, Start- und Änderungszeit, offene Eskalation. Hat Runden.
- **Runde**: Nummer, Stationen, Gesamturteil.
- **Station (Ausführung)**: Rolle, Agent, Modell, Zustand, Start, Dauer, Urteil, Zahl der Muss- und Kann-Befunde.
- **Urteil**: Wert (FR-017), Grund, Befunde.
- **Befund**: Schwere, Ort (Datei/Zeile), Kurzbeschreibung. Nur die Anzahl verlässt das Projekt. Inhalte bleiben lokal.
- **Eskalation**: Zeitpunkt, Runde, Gate-Art, Grund, offen/erledigt.
- **Aufmerksamkeitseintrag**: Art (FR-021), Spec, Grund, Quelle.
- **Marker**: Art (`deploy`/`verified`), Spec-Nummern, Zeitpunkt.
- **Ereignis**: Art (FR-022), Zeitpunkt, Projekt, Lauf-ID, Bezug (Runde, Station), Metadaten.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % der Status-, Stations-, Urteils- und Ereigniswerte aus den ImmoAgent-Verträgen sind in Anhang A zugeordnet oder ausdrücklich als „entfällt“ markiert.
- **SC-002**: Kein Maschinenwert kommt in mehr als einer Ebene vor (Prüfung per Liste).
- **SC-003**: Jeder Zustandsübergang aus dem ImmoAgent-Pilot (Läufe 066, 084, 085, 088, 092) lässt sich mit den erlaubten Übergängen aus FR-011 nachspielen. Das „Parken“ über `aborted` wird dabei durch `paused` ersetzt.
- **SC-004**: Ein Betreiber ordnet in einem Test mit 10 zufällig gewählten Board-Zuständen jeden Wert ohne Nachschlagen der richtigen Ebene zu (≥ 9 von 10).
- **SC-005**: Die Specs 002 bis 007 verwenden ausschließlich Werte aus diesem Vokabular. Die Prüfung erfolgt über `/speckit-analyze` je Spec.

## Assumptions

- Die Stationsbedingungen aus ImmoAgent 092 gelten unverändert. Abweichende Artefaktnamen bei anderen spec-kit-Versionen werden in Spec 005 behandelt.
- Rundenlimit 2, Inaktiv-Schwelle 60 min und Verwaist-Schwelle 6 h sind Defaults. Spec 004 macht sie konfigurierbar.
- Die Lauf-ID nutzt die Sekundengenauigkeit der Startzeit. Kollisionen sind in v1 durch die Projekt-Sperre ausgeschlossen. Für Parallelbetrieb kann später ein Suffix ergänzt werden, ohne das Format zu brechen. Das sichert die Spec zum Parallelbetrieb ab.
- `blocker` und `decision` kommen nur über Plugins (ADR 0001 E6). Ohne Plugin entstehen keine solchen Einträge.
- Die Urteilsform im Prüfer-Antworttext (Zeilenformat) gehört zur Engine (Spec 003). Hier werden nur die Werte festgelegt. Für die Anzeige in `de` bleiben die bekannten Wörter „OK“, „Änderung“ und „Mensch prüft“.

## Anhang A: Zuordnung ImmoAgent → Vokabular v1

| Ebene | ImmoAgent | v1 | Hinweis |
|---|---|---|---|
| Station | `spec` | `specified` | |
| Station | `klaerung` | `clarified` | |
| Station | `plan` | `planned` | |
| Station | `tasks` | `tasked` | |
| Station | `umsetzung` | `implementing` | |
| Station | `umsetzung_fertig` | `implemented` | |
| Station | `deploy` | `deployed` | |
| Station | `live_geprueft` | `verified` | |
| Spec-Status | `done` / `partial` / `not-started` / `no-tasks` | entfällt als eigener Wert | ergibt sich aus Station und Task-Fortschritt |
| Spec-Status | `descoped` | `descoped` = ja | Kennzeichen, keine Station |
| Spec-Wartegrund | `freigabe` / `klaerung` | `approval` / `clarification` | |
| Lauf-Zustand | `building`, `reviewing`, `approved`, `escalated`, `merged`, `aborted`, `reviewed` | gleich | |
| Lauf-Zustand | `aborted` als „geparkt“ (088, 084, 085) | `paused` | neu |
| Lauf-ID | Spec-Verzeichnis | `NNN-YYYYMMDD-HHMMSS` | neu |
| Station-Zustand | `laufend` / `fertig` | `running` / `finished` | |
| Rolle/Station | `builder` / `code` / `ui` | `builder` / `code_review` / `ui_review` | |
| Agent | `pipeline-builder` / `-code-reviewer` / `-ui-reviewer` | Rollenbesetzung | Spec 004 |
| Urteil | `OK` / `Änderung` / `Mensch prüft` | `approve` / `changes_requested` / `needs_human` | |
| Befund | `[Muss]` / `[Kann]` | `must` / `may` | |
| Zähler | `muss_count` / `kann_count` | Anzahl `must` / `may` | Feldnamen in Spec 002 |
| Aufmerksamkeit | `escalated` | `escalation` | |
| Aufmerksamkeit | `freigabe` | `approval` | |
| Aufmerksamkeit | `klaerung` | `clarification` | |
| Aufmerksamkeit | `blocker` / `decision` | `blocker` / `decision` | nur mit Plugin |
| Aufmerksamkeit | `betreiber` (geplant) | `operator_task` | |
| Aufmerksamkeit | — | `stale_run` | neu |
| Ereignis | `run_started` | `run.started` | |
| Ereignis | `round_started` | `round.started` | |
| Ereignis | `station_started` / `station_finished` | `station.started` / `station.finished` | |
| Ereignis | `verdict` | `verdict.recorded` | |
| Ereignis | `escalated` / `released` / `approved` / `merged` / `aborted` | `run.escalated` / `run.released` / `run.approved` / `run.merged` / `run.aborted` | |
| Ereignis | — | `run.paused`, `run.resumed`, `run.returned`, `run.reviewed`, `run.taken_over` | neu |
| Ereignis | `hook_debug` | Diagnose-Ereignis | ohne Statuswirkung |
| Ticker | `commit` / `deploy` / `verified` | Commit / Marker `deploy` / `verified` | Spec 002 |
| Gerüst (verworfen) | `stage: review`, `ui_review`, `operator_wait`; `status: needs_changes`; Rolle `integrator` als aktive Station | entfällt / siehe FR-006, FR-010, FR-015 | Gerüstwerte werden ersetzt |
