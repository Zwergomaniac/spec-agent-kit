# Tasks: Agent-System-Abstraktion fuer Claude und GitHub Copilot

**Input**: Design documents from `/specs/015-copilot-integration/`

**Prerequisites**: `plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/`

**Tests**: Tests sind erforderlich, weil Constitution VII automatisierte Absicherung fuer Contracts, Engine und Init/Upgrade verlangt.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Foundations

**Purpose**: Den agentbezogenen Vertrag und die Grundabstraktion fuer den installierten Zielprojekt-Zustand schaffen, ohne in repo-weiten Multi-Integrationsscope auszuweiten

- [x] T001 Definiere in `packages/contracts/schema/config.schema.json` und bei Bedarf in `packages/contracts/schema/vocabulary.json` genau eine aktiv verwaltete Agent-Umgebung pro Projekt mit mindestens `claude` und `copilot`
- [x] T002 [P] Ergaenze Contract-Beispiele fuer `claude` und `copilot` in `packages/contracts/examples/`, die je Environment den installierten Zielprojekt-Zustand fuer `agents`, `skills`, `hooks`, `instructions` und `settings` ueber konkrete Zielpfade, Zielpfadmuster oder Merge-Ziele abbilden, ohne Beispiele fuer parallele aktive Mehrfachverwaltung mehrerer Agent-Umgebungen einzufuehren
- [x] T003 [P] Aktualisiere Contract-Tests in `packages/contracts/test/` fuer gueltige und ungueltige Agent-Umgebungswerte sowie dafuer, dass der agentbezogene Artefaktvertrag pro Kategorie einen konkreten Pruefgegenstand im Zielprojekt besitzt
- [x] T004 Fuehre in `packages/engine/src/spec_agent_kit/config/` und `packages/engine/src/spec_agent_kit/install/` eine Agent-System-Abstraktion ein, die agentneutrale Konzepte von environment-spezifischen Artefakten trennt
- [x] T004a [P] Definiere in den spaeteren Engine-Vertraegen oder Modellen eine explizite Struktur fuer Artefaktklasse, Zielpfad oder Zielpfadmuster, Verwaltet-vs-Eigen-Abgrenzung und optionales Merge-Ziel je Agent-Umgebung
- [x] T004b [P] Definiere in den spaeteren Engine-Vertraegen oder Modellen eine explizite Paritaetsstruktur mit `capability`, `parity_level`, `mechanism`, `verification_expectation` und Kennzeichnung bewusster Claude-Abweichungen; fuer `hooks` sind nur `full` oder `approximate` zulaessig
- [x] T005 Generiere abgeleitete Contract-Artefakte mit `pnpm contracts:gen` und pruefe sie mit `pnpm contracts:check`

**Checkpoint**: Der Grundvertrag fuer genau eine aktive Agent-Umgebung und deren Agent-Artefaktsatz ist vorhanden

---

## Phase 2: User Story 1 - Projekt fuer die gewaehlte Agent-Umgebung initialisieren und upgraden (Priority: P1)

**Goal**: Agent-Artefakte passend zu `claude` oder `copilot` planen, installieren und konfliktbewusst aktualisieren

**Independent Test**: Ein Projekt kann einmal fuer `claude` und einmal fuer `copilot` initialisiert werden; Upgrade und Re-Init ueberschreiben geaenderte Dateien nicht still.

### Tests for User Story 1

- [x] T006 [P] [US1] Ergaenze Init-/Upgrade-Tests in `packages/engine/tests/install/` fuer environment-spezifische Agent-, Skill-, Hook-, Instruktions- und Settings-Artefakte
- [x] T007 [P] [US1] Ergaenze Tests fuer Konfliktfaelle mit lokal geaenderten verwalteten Agent-Artefakten in `packages/engine/tests/install/`
- [x] T007a [P] [US1] Ergaenze Tests dafuer, dass Init- und Upgrade-Plan je Artefaktklasse konkrete Zielpfade, Zielpfadmuster oder Merge-Ziele im Zielprojekt ausweisen statt nur allgemeine Kategorien

### Implementation for User Story 1

- [x] T008 [P] [US1] Definiere oder ueberarbeite unter `packages/agent-blueprint/templates/claude/` und `packages/agent-blueprint/templates/copilot/` die konkret verwalteten Agent-Artefakte je Agent-Umgebung einschliesslich klarer Zuordnung zu `agents`, `skills`, `hooks`, `instructions` und `settings`
- [x] T009 [US1] Passe `packages/engine/src/spec_agent_kit/install/plan.py`, `packages/engine/src/spec_agent_kit/install/apply.py` und benachbarte Module so an, dass sie den Agent-Artefaktsatz der gewaehlten Agent-Umgebung planen und anwenden
- [x] T010 [US1] Erweitere die Lock- und Upgrade-Logik in `packages/engine/src/spec_agent_kit/install/` fuer environment-spezifische Agent-Artefakte und konfliktbewusste Ersetzungen
- [x] T010a [US1] Stelle in den Install-Modulen sicher, dass Merge-Ziele fuer settings-bezogene Artefakte und die Abgrenzung zu projektseitigen Eigenartefakten explizit im Plan erscheinen

**Checkpoint**: Init und Upgrade verwalten genau den Agent-Artefaktsatz der gewaehlten Agent-Umgebung

---

## Phase 3: User Story 2 - Agent-System agentneutral pruefen und betreiben (Priority: P1)

**Goal**: Config-Check und Doctor von festen Claude-Annahmen entkoppeln und nur fuer die aktive Agent-Umgebung pruefen

**Independent Test**: Ein Claude-Projekt und ein Copilot-Projekt bestehen `sak config check` und `sak doctor`, ohne dass Artefakte der jeweils anderen Agent-Umgebung als Pflichtfehler erscheinen.

### Tests for User Story 2

- [x] T011 [P] [US2] Ergaenze Config-Check-Tests in `packages/engine/tests/config/` fuer Claude- und Copilot-spezifische Agent-Artefakte
- [x] T012 [P] [US2] Ergaenze Doctor-Tests in `packages/engine/tests/install/` oder passenden Testpfaden fuer environment-spezifische Pflicht-, Warn- und Hinweispruefungen
- [x] T012a [P] [US2] Ergaenze Tests dafuer, dass bewusste Copilot-Abweichungen von Claude als `approximate` oder `full` klassifiziert und nicht als unbeabsichtigte Defekte behandelt werden

### Implementation for User Story 2

- [x] T013 [US2] Entkopple `packages/engine/src/spec_agent_kit/config/check.py` von festen Claude-Pfaden und fuehre environment-spezifische Agent-Artefaktpruefungen ein
- [x] T014 [US2] Passe `packages/engine/src/spec_agent_kit/install/doctor.py` so an, dass nur die Artefakte und Faehigkeiten der aktiven Agent-Umgebung validiert werden
- [x] T015 [US2] Modelliere Hook-Unterstuetzung in `packages/engine/src/spec_agent_kit/` als environment-spezifischen Agent-System-Baustein mit nativer oder nativ integrierter Ersatzmechanik; fuer Copilot ist ein Lueckenstatus ausgeschlossen
- [x] T015a [US2] Fuehre in den Validierungsmodulen eine explizite Kennzeichnung fuer bewusste Claude-Abweichungen ein, damit Constitution VI spaeter nachvollziehbar umgesetzt wird

**Checkpoint**: Validierung und Betrieb haengen nicht mehr implizit an Claude-Dateimustern

---

## Phase 4: User Story 3 - Copilot mit hoher funktionaler Paritaet bereitstellen (Priority: P1)

**Goal**: Copilot im Agentensystem mit hoher funktionaler Paritaet zu Claude spezifizieren und pruefbar machen

**Independent Test**: Fuer jeden relevanten Agent-System-Baustein ist die Copilot-Paritaetsstufe benannt und spaeter test- oder doctor-faehig ableitbar.

### Tests for User Story 3

- [x] T016 [P] [US3] Ergaenze Tests in `packages/engine/tests/` oder passenden Testpfaden, die die erwarteten Copilot-Bausteine `agents`, `skills`, `hooks`, `instructions` und `settings` pruefen
- [x] T017 [P] [US3] Ergaenze Tests fuer Copilot-Approximationen, insbesondere die Hook-Ersatzmechanik, damit diese nicht still regressieren
- [x] T017a [P] [US3] Ergaenze Tests fuer die Paritaetskriterien `full` und `approximate`, insbesondere fuer gleiche Pflichtfunktion, benannte Ersatzmechanik und pruefbare Restdifferenz

### Implementation for User Story 3

- [x] T018 [US3] Definiere in den agentbezogenen Engine-Modulen und Vorlagen eine bausteinbezogene Paritaetsmatrix fuer Copilot gegenueber Claude mit expliziten Feldern fuer `capability`, `parity_level`, `claude_mechanism`, `copilot_mechanism`, `verification_expectation` und `intentional_deviation`
- [x] T019 [US3] Implementiere fuer Copilot benoetigte Ersatz- oder Annaeherungsmechaniken in den betroffenen Agent-System-Modulen und Vorlagen
- [x] T020 [US3] Stelle sicher, dass `sak doctor` Copilot nicht pauschal als teilweise unterstuetzt meldet, sondern bausteinbezogen auf Pflicht und Annaeherung verweist; die Hook-Mechanik muss als vorhanden und pruefbar erscheinen
- [x] T020a [US3] Lege fuer `agents`, `skills`, `instructions`, `settings` und `hooks` mindestens `approximate` verbindlich fest; `hooks` duerfen nur als `full` oder `approximate` klassifiziert werden

**Checkpoint**: Copilot-Paritaet ist im Agentensystem konkret und pruefbar beschrieben

---

## Phase 5: Migration & Polish

**Purpose**: Wechsel der Agent-Umgebung absichern und Gesamtvalidierung vorbereiten

- [x] T021 [P] Fuehre Tests fuer den geplanten Wechsel `claude -> copilot` und `copilot -> claude` in `packages/engine/tests/install/` oder passenden Testpfaden ein
- [x] T021a [P] Fuehre Tests dafuer ein, dass der Switch-Fall als eigener Migrationsplan mit `artifacts_to_add`, `artifacts_to_replace`, Konflikten und Betreiberaktionen erscheint statt als stilles Re-Init
- [x] T022 Implementiere oder verfeinere in `packages/engine/src/spec_agent_kit/install/` den konfliktbewussten Wechsel der aktiv verwalteten Agent-Umgebung
- [x] T022a Implementiere fuer den Switch-Fall eine explizite Plan- oder Doctor-Ausgabe, die bewusste Claude-Abweichungen, dokumentierte Copilot-Approximationen und notwendige manuelle Betreiberaktionen sichtbar macht
- [x] T023 [P] Fuehre gezielte Testlaeufe fuer Contracts und Engine aus und behebe verbleibende agentbezogene Regressionen
- [x] T024 Pruefe Repo-Konsistenz fuer die umgesetzten Agent-System-Aenderungen, einschliesslich `pnpm contracts:check`, relevanter Engine-Tests und eines expliziten Checkpoints fuer spaetere README-Statusmatrix-Anpassungen gemaess Constitution VII

## Stand 2026-10-23

- Abgehakt ist nur, was im Repo-Code und in vorhandenen Tests direkt belegbar ist.
- Die Contract-Toolchain ist in dieser Umgebung jetzt repo-konform installiert worden; `pnpm contracts:gen` lief erfolgreich und hat die generierten Dateien fuer `agent_environment` aktualisiert.
- `pnpm contracts:check` laeuft jetzt technisch bis zur Repo-Konsistenzpruefung. In einer uncommitteten Arbeitskopie meldet der Check erwartungsgemaess noch Differenzen der frisch generierten Dateien, bis diese in Git uebernommen werden. Das ist kein versteckter Workaround, sondern die beabsichtigte Check-Semantik.
- Der environment switch hat jetzt eine explizite Migrationszusammenfassung im Upgrade-Plan mit `artifacts_to_add`, `artifacts_to_replace`, `artifacts_to_delete`, Konflikten und Betreiberaktionen statt einer stillen Re-Init-Anmutung.
- `sak doctor` gibt im erkannten Switch-Fall jetzt zusaetzlich eine sichtbare Migrationswarnung mit bewussten Copilot-Approximationen, Claude-Abweichungshinweis und Betreiberaktion aus.
- Gezielte Engine-Regressionstests fuer Upgrade- und Doctor-Switch-Faelle laufen in dieser Umgebung gru en; ein expliziter README-Statusmatrix-Checkpoint bleibt fuer einen spaeteren, separaten README-Abgleich festgehalten, ohne hier unbewiesene Doku-Aussagen einzutragen.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Foundations (Phase 1)**: no dependencies
- **US1, US2, US3 (Phase 2-4)**: depend on Phase 1
- **Migration & Polish (Phase 5)**: depends on completed implementation of the desired user stories

### User Story Dependencies

- **US1** depends on the foundational contract and agent-system abstraction
- **US2** depends on the same foundations and should follow the initial environment-specific install logic
- **US3** depends on the concrete Copilot artifact set and validation model from US1 and US2

### Parallel Opportunities

- T002 and T003 can run in parallel after T001
- T006 and T007 can run in parallel
- T011 and T012 can run in parallel
- T016 and T017 can run in parallel
- T021 and T023 can run in parallel when implementation stabilizes

## Implementation Strategy

### Delivery Strategy

1. Establish the contract for exactly one active agent environment.
2. Make init and upgrade environment-specific for agent artifacts.
3. Make config-check and doctor environment-specific.
4. Add the Copilot parity matrix and any needed approximation mechanisms.
5. Finish with environment-switch safety and regression validation.

### Incremental Delivery

- Increment 1: active agent environment contract plus artifact sets
- Increment 2: environment-specific init and upgrade
- Increment 3: environment-specific validation and hook treatment
- Increment 4: Copilot parity matrix plus migration safety
