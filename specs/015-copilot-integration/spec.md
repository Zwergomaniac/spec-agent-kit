# Feature Specification: Agent-System-Abstraktion fuer Claude und GitHub Copilot

**Feature Branch**: `015-copilot-integration`

**Created**: 2026-10-22

**Status**: Draft

**Input**: Betreiber 2026-10-22. Spec 015 wird neu ausgerichtet. Dieses Repo liefert eine `speckit`-Erweiterung, die in andere Zielprojekte installiert wird. Diese Spec beschreibt deshalb primaer den vertraglich garantierten installierten Zustand im Zielprojekt fuer die Agent-Umgebungen `claude` und `copilot`, nicht einen allgemeinen Multi-Integrationsbetrieb des Repos. Fokus sind Agents, Skills, Hooks sowie die dazugehoerigen Instruktionen und Settings. Ziel ist hohe funktionale Paritaet fuer Copilot innerhalb dieses Agentensystems, ohne unnoetig breiteren Repo-Scope.

## Scope

### In Scope

- Abstraktion des Agentensystems des Kits fuer mindestens zwei Agent-Umgebungen: `claude` und `copilot`
- Blueprint-, Init-, Upgrade- und Doctor-Verhalten, soweit es Agent-Artefakte betrifft
- Verwaltung und Validierung von Agents, Skills, Hooks, Instruktionsdateien und agentbezogenen Settings
- Klare Trennung zwischen agentneutralem Kern und agentumgebungsspezifischen Adaptern oder Vorlagen
- Hohe funktionale Paritaet fuer Copilot innerhalb des Agentensystems des Kits
- Rueckwaertskompatible Weiterfuehrung bestehender Claude-basierten Agent-Projekte

### Out of Scope

- Allgemeiner Multi-Integrationsbetrieb des gesamten Repos
- Gleichzeitige aktive Mehrfachverwaltung mehrerer Agent-Umgebungen im selben Zielprojekt
- Repo-weite Abstraktion aller Produktbereiche wie Dashboard, Push, Board oder Contracts jenseits dessen, was das Agentensystem direkt benoetigt
- Allgemeine Modellabstraktion oder anbieterneutrale Modellprofile
- README-Aenderungen oder andere Repo-Dateien ausserhalb von `specs/015-copilot-integration/`
- Jede Aussage ueber Copilot-Faehigkeiten ausserhalb der hier benoetigten Agent-, Skill-, Hook- und Settings-Mechanik

## Clarifications

### Session 2026-10-22

- Spec 015 beschreibt den garantierten installierten Agent-Zustand im Zielprojekt und kein allgemeines Mehr-Integrationskonzept fuer das Gesamt-Repo.
- Pro Zielprojekt gibt es in 015 genau eine aktiv vom Kit verwaltete Agent-Umgebung.
- Der Kernfokus liegt auf dem Agentensystem: Agents, Skills, Hooks, Instruktionen und Settings.
- Copilot soll im Rahmen dieses Agentensystems eine hohe funktionale Paritaet zu Claude erreichen, aber ohne ungesicherte Behauptung identischer technischer Mechanik.
- Nur Spec-Artefakte unter `specs/015-copilot-integration/` werden in dieser Neufassung bearbeitet.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Projekt fuer die gewaehlte Agent-Umgebung initialisieren und upgraden (Priority: P1)

Ein Betreiber kann ein Zielprojekt mit dem Kit so planen und anwenden, dass die Agent-Artefakte passend zur gewaehlten Agent-Umgebung installiert und spaeter konfliktbewusst aktualisiert werden.

**Why this priority**: Ohne saubere Initialisierung und Upgrade-Pfade bleibt jede Agent-Abstraktion rein konzeptionell und ist operativ nicht nutzbar.

**Independent Test**: Ein Testprojekt wird einmal fuer `claude` und einmal fuer `copilot` geplant und angewendet. Danach existieren im jeweiligen Zielprojekt jeweils nur die zur gewaehlten Agent-Umgebung gehoerenden verwalteten Agent-, Skill-, Hook-, Instruktions- und Settings-Artefakte an den vertraglich vorgesehenen Zielstellen. Ein spaeteres Upgrade zeigt verwaltete Aenderungen an und ueberschreibt keine geaenderten Projektdateien still.

**Acceptance Scenarios**:

1. **Given** ein sauberes Zielprojekt, **When** der Betreiber `sak init` fuer die Agent-Umgebung `claude` plant und anwendet, **Then** installiert das Kit die Claude-spezifischen Agent-System-Artefakte und fuehrt sie als verwaltete Dateien.
2. **Given** ein sauberes Zielprojekt, **When** der Betreiber `sak init` fuer die Agent-Umgebung `copilot` plant und anwendet, **Then** installiert das Kit die Copilot-spezifischen Agent-System-Artefakte und erzwingt keine Claude-Artefakte als Pflichtbestandteil.
3. **Given** ein bereits initialisiertes Projekt mit lokal geaenderten Kit-Artefakten, **When** der Betreiber `sak upgrade` plant, **Then** zeigt das Kit Konflikte oder Ersetzungen explizit an und ueberschreibt nichts still.

---

### User Story 2 - Agent-System agentneutral pruefen und betreiben (Priority: P1)

Ein Betreiber kann das Agentensystem des Kits fuer Claude oder Copilot nutzen, ohne dass die Validierung oder Laufzeitannahmen fest auf Claude-Dateinamen, Claude-Hooks oder Claude-Settings verankert bleiben.

**Why this priority**: Der eigentliche Nutzen der Spec liegt in einer sauberen Agent-System-Abstraktion. Copilot-Unterstuetzung darf nicht auf einem versteckten Claude-Zwang beruhen.

**Independent Test**: Ein Claude-Projekt und ein Copilot-Projekt bestehen jeweils `sak config check` und `sak doctor`, wobei nur die fuer die gewaehlte Agent-Umgebung relevanten Agent-Artefakte und Faehigkeiten geprueft werden.

**Acceptance Scenarios**:

1. **Given** ein Projekt mit Agent-Umgebung `claude`, **When** `sak config check` und `sak doctor` laufen, **Then** pruefen sie die Claude-spezifischen Agent-System-Artefakte und Faehigkeiten korrekt.
2. **Given** ein Projekt mit Agent-Umgebung `copilot`, **When** `sak config check` und `sak doctor` laufen, **Then** pruefen sie die Copilot-spezifischen Agent-System-Artefakte und melden fehlende Claude-Artefakte nicht als Pflichtfehler.
3. **Given** eine Agent-Umgebung, in der einzelne Komfortfunktionen anders oder eingeschraenkt abgebildet werden, **When** das Kit diese prueft, **Then** unterscheidet es zwischen Pflichtmechanik, optionaler Faehigkeit und nicht verfuegbarer Paritaetsfunktion.

---

### User Story 3 - Copilot mit hoher funktionaler Paritaet im Agentensystem bereitstellen (Priority: P1)

Ein Betreiber kann Copilot im Rahmen des Agentensystems des Kits mit hoher funktionaler Paritaet zu Claude nutzen, insbesondere fuer Rollenartefakte, Skills, Hook-Anbindung oder deren definierte Ersatzmechanik sowie die benoetigten Instruktionen und Settings.

**Why this priority**: Die korrigierte Zielsetzung verlangt keinen allgemeinen Integrationsausbau des Repos, sondern eine starke Copilot-Unterstuetzung innerhalb des Agentensystems.

**Independent Test**: Fuer Copilot ist dokumentiert und pruefbar, welche Agent-System-Funktionen voll unterstuetzt sind und welche ueber eine andere technische Abbildung erreicht werden. `sak doctor` und die Quickstart-Szenarien koennen diese Matrix nachvollziehen, einschliesslich der Hook-Ersatzmechanik, falls keine native Hook-Form genutzt wird.

**Acceptance Scenarios**:

1. **Given** die Spezifikation der Copilot-Agent-Umgebung, **When** der Betreiber die vorgesehenen Agent-Artefakte betrachtet, **Then** sind Agents, Skills, Hook-Anbindung oder Hook-Ersatz, Instruktionen und Settings konkret benannt.
2. **Given** eine Funktion des Claude-Agentensystems, **When** es fuer Copilot keine identische technische Mechanik gibt, **Then** beschreibt die Spec die vorgesehene gleichwertige oder angenaeherte Abbildung und stuft verbleibende Unterschiede explizit ein.
3. **Given** ein Copilot-Projekt, **When** `sak doctor` oder spaetere Tests laufen, **Then** koennen sie die erwartete Paritaetsstufe je Agent-System-Baustein pruefen, statt Copilot nur pauschal als teilweise unterstuetzt zu behandeln.

## Edge Cases

- Ein Zielprojekt besitzt bereits eigene Agents, Skills oder Hooks, die nicht vom Kit stammen.
- Eine Agent-Umgebung erlaubt keine Hook-Mechanik, die Claude formal entspricht, aber eine fachlich gleichwertige und pruefbare native oder nativ integrierte Ersatzmechanik ist moeglich.
- Eine Agent-Umgebung benoetigt andere Dateinamen oder Verzeichnisstrukturen fuer Instruktionen und Settings.
- Ein Betreiber moechte die Agent-Umgebung in einem bereits initialisierten Projekt von `claude` auf `copilot` oder umgekehrt umstellen.
- Ein Upgrade trifft auf lokal geaenderte agentbezogene Settings-Fragmente oder Instruktionsdateien.
- Copilot erreicht fuer einen Baustein nur angenaeherte statt vollstaendige Paritaet; die Spec muss dies als bewusste Approximation statt als implizite Gleichheit ausweisen.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Das Kit MUSS sein Agentensystem explizit von der konkreten Agent-Umgebung abstrahieren.
- **FR-002**: Das Kit MUSS mindestens die Agent-Umgebungen `claude` und `copilot` unterstuetzen.
- **FR-003**: Ein Zielprojekt MUSS in 015 genau eine aktiv vom Kit verwaltete Agent-Umgebung haben.
- **FR-004**: `sak init` und `sak upgrade` MUESSEN die verwalteten Agent-, Skill-, Hook-, Instruktions- und Settings-Artefakte passend zur gewaehlten Agent-Umgebung planen und anwenden.
- **FR-005**: Das Kit DARF fuer eine Copilot-Konfiguration keine Claude-Artefakte als Pflichtbestandteil verlangen.
- **FR-006**: Das Kit MUSS bestehende Claude-basierte Agent-Projekte weiterhin unterstuetzen, ohne deren verwaltete Agent-Artefakte still umzudeuten oder zu ueberschreiben.
- **FR-007**: `sak config check` und `sak doctor` MUESSEN agentumgebungsspezifisch validieren und nur die jeweils relevanten Agent-System-Artefakte und Faehigkeiten pruefen.
- **FR-008**: Die Spec MUSS fuer jede unterstuetzte Agent-Umgebung die verwalteten Agent-System-Artefakte konkret benennen. Dazu gehoeren mindestens Agents, Skills, Hooks oder Hook-Ersatzmechaniken, Instruktionen und agentbezogene Settings.
- **FR-008a**: Fuer jede Artefaktkategorie MUSS die Spec einen verbindlichen Pruefgegenstand im Zielprojekt definieren: entweder den konkreten verwalteten Zielpfad, ein verbindliches Zielpfadmuster oder eine eindeutig benannte Merge- oder Validierungsstelle im Zielprojekt.
- **FR-008b**: Solange exakte finale Dateinamen noch nicht verantwortbar sind, MUSS die Spec mindestens die Artefaktklasse, den Zielbereich je Agent-Umgebung im installierten Zielprojekt und die spaeter pruefbare Abgrenzung zwischen vom Kit verwalteten Dateien und projektseitigen Eigenartefakten normativ festlegen. Repo- oder Template-Pfade duerfen dabei nur als Herleitung oder Quelle dienen.
- **FR-009**: Das Kit MUSS zwischen Pflichtmechanik, optionalen Faehigkeiten und dokumentierten Paritaetsabweichungen unterscheiden koennen.
- **FR-010**: Fuer Copilot MUSS eine hohe funktionale Paritaet zum Claude-Agentensystem angestrebt und bausteinbezogen beschrieben werden.
- **FR-011**: Wenn fuer Copilot keine identische technische Mechanik wie bei Claude verfuegbar ist, MUSS die Loesung eine definierte Ersatz- oder Annaeherungsmechanik spezifizieren, die denselben Kit-Zweck im Zielprojekt fachlich abbildet und pruefbar macht.
- **FR-011a**: Die Copilot-Paritaet MUSS pro relevantem Baustein mindestens `agents`, `skills`, `hooks`, `instructions` und `settings` einzeln klassifiziert werden.
- **FR-011b**: `full` darf nur verwendet werden, wenn der Baustein fuer Copilot ohne manuelle Betreiber-Ausweichschritte denselben Kit-Zweck erfuellt und durch dieselbe Test- oder Doctor-Klasse als Pflichtpruefung absicherbar ist.
- **FR-011c**: `approximate` darf nur verwendet werden, wenn der Baustein den Kit-Zweck mit einer explizit benannten Ersatz- oder Annaeherungsmechanik erfuellt, dabei bekannte Unterschiede dokumentiert sind und `sak doctor` oder spaetere Tests diese Abbildung gezielt pruefen koennen.
- **FR-011d**: Fuer Copilot-Hooks ist `gap` in 015 unzulaessig. Falls keine identische native Hook-Form existiert, MUSS eine native oder nativ integrierte Hook-Ersatzmechanik festgelegt werden, die die Claude-Hook-Semantik so weit wie praktisch moeglich abbildet und pruefbar macht.
- **FR-012**: Die Loesung MUSS die Hoheit des Zielprojekts wahren: eigene Projektdateien bleiben unangetastet, Konflikte werden sichtbar geplant, und es gibt keine stillen Ueberschreibungen.
- **FR-013**: Die Loesung DARF den Scope nicht auf allgemeine Repo-Mehrfachintegrationen, Dashboard-Erweiterungen oder allgemeine Modellabstraktion ausweiten.
- **FR-014**: Die Loesung DARF keine neuen Metadatenpfade einfordern, die Code, Prompts, Diffs oder Secrets an Dashboard oder Events uebertragen.
- **FR-015**: Bewusste Abweichungen von der Claude-Referenz MUESSEN in den Spec-Artefakten je Baustein explizit als Designentscheidung markiert werden; sie duerfen nicht als versehentliche Unterstuetzungsluecke erscheinen.
- **FR-016**: Die Spec-Artefakte MUESSEN fuer spaetere Umsetzung festhalten, dass jede Aenderung mit Auswirkungen auf die README-Statusmatrix vor Abschluss der Implementierung in den Umsetzungsarbeiten eingeplant und geprueft werden MUSS, ohne in dieser Spec README-Inhalte zu aendern.
- **FR-017**: Der Wechsel der aktiv verwalteten Agent-Umgebung MUSS als eigener Migrationsfall mit Plan-, Konflikt-, Ersetzungs- und Validierungsanforderungen beschrieben sein; er DARF nicht als stilles Re-Init modelliert werden.

### Normative Artifact Definitions

Die folgenden Definitionen legen fuer diese Spec den minimal verbindlichen Pruefgegenstand im installierten Zielprojekt fest. Wo die Umsetzung spaeter exakte Dateinamen waehlt, darf sie diese nur innerhalb der hier beschriebenen Artefaktklasse und des angegebenen Zielbereichs konkretisieren. Repo- oder Template-Pfade benennen nur die Quelle, nicht den normativen Soll-Zustand.

#### Claude Managed Artifact Contract

| Kategorie | Verbindlicher Pruefgegenstand im Zielprojekt | Repo- oder Template-Quelle |
|---|---|---|
| Agents | Verwaltete Claude-Rollen- oder Agent-Artefakte erscheinen nur an den fuer die aktive Claude-Umgebung vorgesehenen Zielstellen des Zielprojekts | `packages/agent-blueprint/templates/claude/**` |
| Skills | Verwaltete Claude-Skill-Artefakte erscheinen nur an den fuer die aktive Claude-Umgebung vorgesehenen Zielstellen des Zielprojekts | `packages/agent-blueprint/templates/claude/**` |
| Hooks | Native Claude-Hook-Artefakte oder deren eindeutig benannte Hook-Konfiguration erscheinen nur an den fuer Claude vorgesehenen Zielstellen des Zielprojekts | `packages/agent-blueprint/templates/claude/**` |
| Instructions | Claude-spezifische Instruktionsdateien oder Instruktionsfragmente erscheinen als verwaltete Artefakte an den fuer Claude vorgesehenen Zielstellen des Zielprojekts | `packages/agent-blueprint/templates/claude/**` |
| Settings | Claude-bezogene Settings-Artefakte erscheinen als verwaltete Zielartefakte oder ueber eine explizit benannte Merge-Stelle im Zielprojekt | `packages/agent-blueprint/templates/claude/**` oder `packages/agent-blueprint/templates/config/**` |

#### Copilot Managed Artifact Contract

| Kategorie | Verbindlicher Pruefgegenstand im Zielprojekt | Repo- oder Template-Quelle |
|---|---|---|
| Agents | Verwaltete Copilot-Rollen- oder Agent-Artefakte erscheinen nur an den fuer die aktive Copilot-Umgebung vorgesehenen Zielstellen des Zielprojekts | `packages/agent-blueprint/templates/copilot/**` |
| Skills | Verwaltete Copilot-Skill-Artefakte oder funktional gleichwertige, klar als Skill-Ersatz deklarierte Bausteine erscheinen nur an den vorgesehenen Zielstellen des Zielprojekts | `packages/agent-blueprint/templates/copilot/**` |
| Hooks | Copilot erhaelt im Zielprojekt entweder native Hook-Artefakte oder eine klar benannte native oder nativ integrierte Hook-Ersatzmechanik fuer denselben Kit-Zweck | `packages/agent-blueprint/templates/copilot/**` |
| Instructions | Copilot-spezifische Instruktionsdateien oder Instruktionsfragmente erscheinen als verwaltete Artefakte an den fuer Copilot vorgesehenen Zielstellen des Zielprojekts | `packages/agent-blueprint/templates/copilot/**` |
| Settings | Copilot-bezogene Settings-Artefakte erscheinen als verwaltete Zielartefakte oder ueber eine explizit benannte Merge-Stelle im Zielprojekt | `packages/agent-blueprint/templates/copilot/**` oder `packages/agent-blueprint/templates/config/**` |

#### Artifact Boundary Rules

- Das Kit MUSS je Agent-Umgebung genau den verwalteten Artefaktsatz aus den oben definierten Kategorien verfolgen; projektseitige Eigenartefakte ausserhalb des geplanten verwalteten Satzes bleiben unangetastet.
- Spaetere Umsetzung und Tests MUESSEN pro Kategorie mindestens einen konkret benannten Pfad oder ein Pfadmuster im Zielprojekt nachweisen koennen.
- Wenn Settings nicht als einzelne Datei installiert, sondern in ein Zielartefakt gemergt werden, MUSS diese Merge-Stelle explizit benannt und spaeter testbar sein.

### Copilot Parity Classification

Die Paritaetsklassifikation beschreibt funktionale Paritaet innerhalb des Agentensystems, nicht technische Identitaet der zugrunde liegenden Agent-Plattform.

| Baustein | Claude-Referenz | Copilot-Mindestfestlegung in dieser Spec | Zulaessige Einstufungen |
|---|---|---|---|
| `agents` | Claude-Rollen- oder Agent-Artefakte im verwalteten Satz | Copilot MUSS einen verwalteten Rollen- oder Agent-Mechanismus fuer dieselben Kit-Rollen erhalten | `full` oder `approximate` |
| `skills` | Claude-Skill-Artefakte im verwalteten Satz | Copilot MUSS verwaltete Skill-Artefakte oder klar benannte Skill-Ersatzbausteine erhalten | `full` oder `approximate` |
| `hooks` | Claude-Hook-Anbindung als Teil des Agentensystems | Copilot MUSS entweder native Hook-Anbindung oder eine explizite native oder nativ integrierte Hook-Ersatzmechanik erhalten, die die Claude-Hook-Semantik so weit wie praktisch moeglich abbildet | `full`, `approximate` |
| `instructions` | Claude-Instruktionsartefakte fuer Rollen- und Arbeitssteuerung | Copilot MUSS verwaltete Instruktionsartefakte fuer dieselbe Kit-Steuerungsfunktion erhalten | `full` oder `approximate` |
| `settings` | Claude-settings-bezogene Integrations- und Schutzregeln | Copilot MUSS settings-bezogene Integrations- und Schutzregeln mit gleicher Sicherheitsabsicht erhalten | `full` oder `approximate` |

#### Current Spec-Level Parity Commitments

- `agents`: mindestens `approximate`; ein verbleibendes `gap` ist fuer diesen Kernbaustein in 015 nicht zulaessig.
- `skills`: mindestens `approximate`; Ersatz ueber Instruktionsbausteine ist nur zulaessig, wenn die Skill-Funktion dennoch einzeln pruefbar bleibt.
- `hooks`: mindestens `approximate`; `gap` ist fuer Copilot-Hooks in 015 ausgeschlossen. Falls keine identische native Hook-Form existiert, MUSS eine native oder nativ integrierte, pruefbare Ersatzmechanik den Kit-Zweck abbilden.
- `instructions`: mindestens `approximate`; die Rollen- und Arbeitssteuerung darf nicht unklassifiziert bleiben.
- `settings`: mindestens `approximate`; gleiche Sicherheitsabsicht ist Pflicht, auch wenn die technische Form abweicht.

### Constitution Alignment Notes

- **Constitution VI - bewusste Abweichungen von der Claude-Referenz**: Claude bleibt Referenz. Jede spaetere Copilot-Abweichung von Claude-Dateistruktur, Hook-Mechanik oder Settings-Form gilt nur dann als konform, wenn sie in der Paritaetsklassifikation als bewusste `approximate`- oder `full`-Entscheidung mit benannter Zielprojekt-Mechanik dokumentiert wird.
- **Constitution VII - README-Statusmatrix**: Diese Spec aendert die README nicht. Sie verpflichtet die spaetere Umsetzung jedoch, vor Abschluss der Implementierung die notwendigen README-Statusmatrix-Anpassungen zu identifizieren und als Umsetzungsarbeit mitzupruefen, damit keine spezifizierte Funktion ohne Repo-Statusabgleich landet.

### Key Entities *(include if feature involves data)*

- **Agent Environment**: Eine konkrete Agent-Umgebung, die das Kit fuer sein Agentensystem unterstuetzt, z. B. `claude` oder `copilot`.
- **Agent System Adapter**: Die Abbildung zwischen agentneutralen Kit-Konzepten und den konkreten Dateien, Regeln und Faehigkeiten einer Agent-Umgebung.
- **Managed Agent Artifact Set**: Die Menge der vom Kit verwalteten Agent-, Skill-, Hook-, Instruktions- und Settings-Artefakte einer Agent-Umgebung.
- **Parity Capability**: Ein einzelner Agent-System-Baustein, fuer den festgehalten wird, ob Copilot volle Paritaet oder eine definierte Annaeherung gegenueber Claude erreicht.
- **Environment Switch Plan**: Der geplante, konfliktbewusste Wechsel eines Zielprojekts von einer verwalteten Agent-Umgebung auf eine andere.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Ein Testprojekt kann mit `sak init` einmal fuer `claude` und einmal fuer `copilot` geplant und angewendet werden, wobei jeweils nur die zur gewaehlten Agent-Umgebung gehoerenden Agent-System-Artefakte als verwaltet erscheinen.
- **SC-002**: `sak config check` und `sak doctor` liefern fuer ein Claude-Projekt und fuer ein Copilot-Projekt korrekte, agentumgebungsspezifische Ergebnisse ohne Fehlalarme wegen Artefakten der jeweils anderen Agent-Umgebung.
- **SC-003**: Die Spec benennt fuer `claude` und `copilot` jeweils die im Zielprojekt verwalteten Agents, Skills, Hooks oder Hook-Ersatzmechaniken, Instruktionen und Settings so konkret, dass spaetere Tests sie direkt validieren koennen.
- **SC-004**: Fuer jeden als relevant definierten Agent-System-Baustein des Copilot-Pfads ist dokumentiert, ob volle Paritaet oder definierte Annaeherung gilt, einschliesslich der Kriterien fuer `full` und `approximate`; fuer `hooks` ist eine pruefbare Ersatzmechanik Pflicht, falls keine identische native Hook-Form existiert.
- **SC-005**: Ein geaendertes Zielprojekt erhaelt bei `sak upgrade` oder beim Wechsel der Agent-Umgebung einen expliziten Plan fuer Konflikte oder Ersetzungen; keine verwaltete Datei wird still ueberschrieben.
- **SC-006**: Die Spec-Artefakte fuer 015 enthalten keine Anforderungen mehr an parallele aktive Mehrfachverwaltung mehrerer Agent-Umgebungen im selben Zielprojekt, keine allgemeinen Repo-Multi-Integrationsziele und keine allgemeine Modellabstraktion.
- **SC-007**: Die Spec-Artefakte halten explizit fest, welche bewussten Copilot-Abweichungen von Claude spaeter zulaessig sind und dass README-Statusfolgen vor Abschluss der Implementierung geprueft werden muessen.

## Assumptions

- Claude bleibt die bestehende Referenz des Agentensystems; Copilot wird daran funktional gespiegelt, nicht zwingend mechanisch identisch.
- Das Kit kann nur das abstrahieren, was an einer Agent-Umgebung technisch beobachtbar oder vertraglich stabil genug ist.
- Agentbezogene Settings und Instruktionsdateien koennen sich zwischen Agent-Umgebungen deutlich unterscheiden, ohne den agentneutralen Kern zu verletzen.
- Ein Wechsel der aktiv verwalteten Agent-Umgebung ist ein geplanter Migrationsfall, kein stiller Hintergrundwechsel.
