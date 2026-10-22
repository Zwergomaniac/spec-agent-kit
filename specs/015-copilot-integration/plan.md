# Implementation Plan: Agent-System-Abstraktion fuer Claude und GitHub Copilot

**Branch**: `015-copilot-integration` | **Date**: 2026-10-22 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/015-copilot-integration/spec.md`

## Summary

Spec 015 abstrahiert das Agentensystem des Spec Agent Kit von einer implizit Claude-zentrierten Struktur zu einem agentneutralen Kern mit agentumgebungsspezifischen Adaptern fuer `claude` und `copilot`. Normativ beschrieben wird der installierte Soll-Zustand im Zielprojekt je Agent-Umgebung; Repo- und Template-Pfade sind nur die Herleitung dafuer. Der Fokus liegt ausschliesslich auf Agents, Skills, Hooks sowie den dazugehoerigen Instruktionen und Settings. Die Planung schliesst ausdruecklich einen allgemeinen Repo-weiten Multi-Integrationsbetrieb, parallele aktive Mehrfachverwaltung mehrerer Agent-Umgebungen im selben Zielprojekt und eine allgemeine Modellabstraktion aus. Copilot soll innerhalb dieses Agentensystems eine hohe funktionale Paritaet zu Claude erreichen, mit expliziter Benennung von Vollparitaet und Annaeherung; fuer Hooks ist `gap` ausgeschlossen.

## Critical Review Of Previous Draft

- Der bisherige Entwurf war zu breit und verschob 015 in Richtung eines allgemeinen Multi-Integrationsbetriebs fuer das gesamte Repo.
- Die Annahme, mehrere Agent-Umgebungen muessten im selben Zielprojekt gleichzeitig voll verwaltet werden, widerspricht der korrigierten Zielsetzung.
- Die bisherige Modellabstraktion ueber Profile und Anbieterneutralitaet war ausserhalb des neuen Fokus.
- Doku-Aenderungen an `README.md`, `docs/architecture.md`, `CLAUDE.md` und weiteren Repo-Dateien lagen ausserhalb des jetzt geforderten Bearbeitungsbereichs.
- Mehrere Aussagen vermischten Agentensystem-Abstraktion mit Repo-weiten Teilbereichen wie Board, Push und Dashboard, obwohl diese nur indirekt betroffen sind.

## Technical Context

**Language/Version**: Python 3.11+ fuer die Engine, TypeScript/Node 22+ fuer Contracts und Blueprint-bezogene Pakete

**Primary Dependencies**: bestehende Engine-Abhaengigkeiten (`pyyaml`, `jsonschema`, Standardbibliothek) sowie bestehendes Workspace-Tooling; keine neuen Technologieentscheidungen durch diese Spec

**Storage**: verwaltete Dateien im Zielprojekt fuer Agent-Artefakte; keine neue persistente Datenhaltung vorgesehen

**Testing**: Contract-Tests, Engine-Tests fuer Config/Install/Doctor, Smoke-Tests fuer Init und Upgrade, Fixture- oder Golden-Tests fuer agentumgebungsspezifische Artefakte

**Target Platform**: Windows, Linux und macOS fuer das Kit; unterstuetzte Agent-Umgebungen sind Claude und GitHub Copilot

**Project Type**: Monorepo mit Python-Engine und Blueprint-Templates

**Performance Goals**: keine spuerbare Regression bei `sak init`, `sak upgrade`, `sak config check` und `sak doctor`

**Constraints**:

- Nur Agentensystem-Scope, keine allgemeine Repo-Mehrfachintegration
- Pro Zielprojekt genau eine aktiv verwaltete Agent-Umgebung
- Keine stillen Ueberschreibungen im Zielprojekt
- Keine neuen Metadateninhalte mit Code, Prompts oder Secrets
- Keine Aenderungen ausserhalb von `specs/015-copilot-integration/` in dieser Planfassung

**Scale/Scope**: Aenderungen an Config-/Install-/Doctor-Vertraegen und Blueprint-Struktur nur soweit noetig, um das Agentensystem fuer `claude` und `copilot` zu abstrahieren

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I. Contracts zuerst**: Falls Config- oder Vokabularaenderungen fuer die Agent-Umgebungswahl oder deren Artefaktvertrag noetig sind, beginnen sie in `packages/contracts`. Besteht.
- **II. Nur Metadaten**: Die Spec fordert keine neuen Inhalte mit Code, Diffs, Prompts oder Secrets. Besteht.
- **III. Hoheit des Zielprojekts**: Init und Upgrade bleiben konfliktbewusst; eigene Agents, Skills und Hooks des Zielprojekts bleiben unangetastet. Besteht.
- **IV. Sicherer Default**: Sicherheitssemantik agentbezogener Settings bleibt erhalten; Copilot darf keine lockereren Defaults erzwingen. Besteht.
- **V. Planen und Umsetzen getrennt**: Diese Artefakte bleiben rein spezifikativ. Besteht.
- **VI. Erprobtes uebernehmen**: Bestehende Claude-Mechanik bleibt Referenz und wird abstrahiert statt ersetzt. Besteht.
- **VII. Testbar und ehrlich**: Die Spec benennt spaetere Tests fuer Contracts, Engine und Init/Upgrade/Doctor; sie behauptet keine unbewiesene Vollgleichheit. Besteht.
- **VIII. Generisch mit Erweiterungspunkten**: Die Agent-System-Abstraktion staerkt genau dieses Prinzip und vermeidet Repo-weite Ueberdehnung. Besteht.

**Post-Design Check**: Weiterhin bestanden, sofern die Umsetzung keine parallele Mehrfachverwaltung mehrerer Agent-Umgebungen einfuehrt und Copilot-Paritaet bausteinbezogen statt pauschal behauptet.

## Project Structure

### Documentation (this feature)

```text
specs/015-copilot-integration/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/
`-- tasks.md
```

### Source Areas Impacted By Later Implementation

```text
packages/
|-- contracts/
|   |-- schema/
|   `-- test/
|-- engine/
|   |-- src/spec_agent_kit/config/
|   |-- src/spec_agent_kit/install/
|   |-- src/spec_agent_kit/pipeline/
|   `-- tests/
`-- agent-blueprint/
    `-- templates/
        |-- claude/
        |-- copilot/
        `-- config/
```

**Structure Decision**: Spaetere Umsetzung beruehrt primaer Contracts, Engine und Agent-Blueprints. Diese Spec fuehrt aber keine Anforderungen ein, die README, Dashboard oder allgemeine Repo-Dokumente anpassen muessen.

## Phase 0: Research Outcome

Die offenen Architekturfragen wurden in `research.md` geklaert:

- Das Agentensystem wird klar vom restlichen Repo-Scope getrennt.
- Pro Zielprojekt gibt es genau eine aktiv verwaltete Agent-Umgebung.
- Agent-Artefakte werden pro Agent-Umgebung beschrieben und validiert.
- Hook-Mechanik wird als agentumgebungsspezifischer Baustein mit nativer oder nativ integrierter Ersatzmechanik behandelt; ein fehlender Hook-Baustein ist fuer Copilot in 015 nicht zulaessig.
- Copilot wird mit hoher funktionaler Paritaet innerhalb des Agentensystems spezifiziert, nicht als repo-weites Integrationsprogramm.

## Phase 1 Design Artifacts

### Design Decisions

1. **Agent Environment statt allgemeinem Integrationssatz**
   - Das Projekt waehlt genau eine aktiv verwaltete Agent-Umgebung.
   - Ein geplanter Environment-Wechsel ist erlaubt, aber keine parallele Vollverwaltung.

2. **Agent-System-Adapter pro Agent-Umgebung**
   - `claude` und `copilot` erhalten klar getrennte Artefaktdefinitionen.
   - Der Kern beschreibt nur agentneutrale Konzepte wie Agent, Skill, Hook, Instruktion und Settings-Semantik.

3. **Bausteinbezogene Paritaetsmatrix fuer Copilot**
     - Fuer jeden relevanten Agent-System-Baustein wird dokumentiert, ob Copilot Vollparitaet oder Annaeherung erreicht.
     - Fehlende identische Mechaniken werden nicht versteckt, sondern als Ersatz- oder Annaeherungsmechanik geplant.
     - Die Paritaetsstufen werden operationalisiert: `full` nur bei gleicher Pflichtfunktion ohne Betreiber-Workaround, `approximate` nur mit benannter Ersatzmechanik und pruefbarer Restdifferenz.
     - Fuer `hooks` ist nur `full` oder `approximate` zulaessig; `approximate` setzt eine native oder nativ integrierte, pruefbare Mechanik voraus.

4. **Validierung nur fuer die gewaehlte Agent-Umgebung**
   - `sak config check` und `sak doctor` pruefen nur die Artefakte und Faehigkeiten der aktiven Agent-Umgebung.
   - Claude-spezifische Fehler duerfen Copilot-Projekte nicht blockieren und umgekehrt.

5. **Migration statt paralleler Mehrfachverwaltung**
    - Ein Wechsel zwischen `claude` und `copilot` wird als geplanter Migrationsfall beschrieben.
    - Konflikte und Ersetzungen muessen sichtbar geplant werden.

6. **Normativer Artefaktvertrag statt loser Kategorien**
   - Die Spec legt pro Agent-Umgebung fuer `agents`, `skills`, `hooks`, `instructions` und `settings` einen verbindlichen Pruefgegenstand fest.
   - Wenn exakte Dateinamen noch nicht verantwortbar sind, werden mindestens Wurzelbereich, Pfadmuster, Merge-Ziel und spaetere Pruefbarkeit normativ festgelegt.

7. **Constitution-Spannungen explizit im Design behandeln**
   - Bewusste Copilot-Abweichungen von Claude werden als Designentscheidungen dokumentiert statt stiller Implizitabweichung.
   - README-Statusmatrix-Folgen werden als spaeterer Implementierungs-Checkpoint festgehalten, ohne in dieser Spec ausserhalb des erlaubten Bereichs zu editieren.

### Normative Artifact Design Baseline

Die Umsetzung von 015 darf den Artefaktvertrag spaeter nur konkretisieren, nicht wieder verallgemeinern. Normativ massgeblich ist immer der installierte Zustand im Zielprojekt.

| Environment | Artifact Class | Spec-Level Binding im Zielprojekt |
|---|---|---|
| `claude` | `agents` | verwaltete Claude-Agent-Artefakte liegen nur an den fuer Claude vorgesehenen Zielstellen des Zielprojekts; Quelle: `packages/agent-blueprint/templates/claude/**` |
| `claude` | `skills` | verwaltete Claude-Skill-Artefakte liegen nur an den fuer Claude vorgesehenen Zielstellen des Zielprojekts; Quelle: `packages/agent-blueprint/templates/claude/**` |
| `claude` | `hooks` | native Claude-Hook-Artefakte oder klar benannte Hook-Konfiguration liegen an den fuer Claude vorgesehenen Zielstellen des Zielprojekts; Quelle: `packages/agent-blueprint/templates/claude/**` |
| `claude` | `instructions` | verwaltete Claude-Instruktionsartefakte liegen an den fuer Claude vorgesehenen Zielstellen des Zielprojekts; Quelle: `packages/agent-blueprint/templates/claude/**` |
| `claude` | `settings` | verwaltete Claude-Settings-Artefakte liegen als Zielartefakte oder ueber explizite Merge-Ziele im Zielprojekt vor; Quelle: `packages/agent-blueprint/templates/claude/**` oder `packages/agent-blueprint/templates/config/**` |
| `copilot` | `agents` | verwaltete Copilot-Agent-Artefakte liegen nur an den fuer Copilot vorgesehenen Zielstellen des Zielprojekts; Quelle: `packages/agent-blueprint/templates/copilot/**` |
| `copilot` | `skills` | verwaltete Copilot-Skill-Artefakte oder klar deklarierte Skill-Ersatzbausteine liegen an den fuer Copilot vorgesehenen Zielstellen des Zielprojekts; Quelle: `packages/agent-blueprint/templates/copilot/**` |
| `copilot` | `hooks` | Copilot-Hooks liegen im Zielprojekt als native Hook-Artefakte oder als klar deklarierte native oder nativ integrierte Ersatzmechanik vor; Quelle: `packages/agent-blueprint/templates/copilot/**` |
| `copilot` | `instructions` | verwaltete Copilot-Instruktionsartefakte liegen an den fuer Copilot vorgesehenen Zielstellen des Zielprojekts; Quelle: `packages/agent-blueprint/templates/copilot/**` |
| `copilot` | `settings` | verwaltete Copilot-Settings-Artefakte liegen als Zielartefakte oder ueber explizite Merge-Ziele im Zielprojekt vor; Quelle: `packages/agent-blueprint/templates/copilot/**` oder `packages/agent-blueprint/templates/config/**` |

### Verification Consequences

- Init- und Upgrade-Tests muessen den verwalteten Satz pro Artefaktklasse nachweisen, nicht nur die Existenz irgendeiner environment-spezifischen Datei.
- Config-Check und Doctor muessen dieselben Artefaktklassen mit Pflicht- oder Approximation-Semantik auswerten koennen; fuer Hooks muss die Ersatzmechanik konkret pruefbar sein.
- Die Implementierung braucht eine explizite Stelle fuer bewusste Claude-Abweichungen und fuer dokumentierte Copilot-Approximationen, insbesondere im Hook-Baustein.
- Vor Abschluss der spaeteren Implementierung ist ein README-Statusmatrix-Checkpoint noetig, auch wenn diese Planfassung noch keine README-Aenderung erzeugt.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Keine | - | - |
