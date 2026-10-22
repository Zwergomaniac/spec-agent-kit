# Contract Notes: Agent-System-Abstraktion fuer Claude und GitHub Copilot

## Scope

Dieser Vertrag betrifft nur den agentbezogenen Teil des Kits: Agents, Skills, Hooks, Instruktionen und agentbezogene Settings. Normativ beschrieben wird der installierte Zustand im Zielprojekt; Repo- und Template-Pfade sind nur Quellenverweise.

## Contract Changes

### Agent Environment Selection

- Die Projektkonfiguration benennt genau eine aktiv verwaltete Agent-Umgebung.
- Unterstuetzte Werte umfassen mindestens `claude` und `copilot`.
- Init, Upgrade, Config-Check und Doctor muessen diese Auswahl konsistent auswerten.
- Diese Spec fuehrt keinen Integrationssatz und keine parallele aktive Mehrfachverwaltung im selben Zielprojekt ein.

### Managed Agent Artifact Sets

- Fuer jede unterstuetzte Agent-Umgebung gibt es einen konkret benannten Satz verwalteter Agent-Artefakte.
- Dieser Satz umfasst mindestens:
  - Agents
  - Skills
  - Hooks oder Hook-Ersatzmechaniken
  - Instruktionen
  - agentbezogene Settings oder Settings-Merge-Ziele
- Fuer jede dieser Kategorien muss der Vertrag einen verbindlichen Pruefgegenstand im Zielprojekt enthalten: konkreter Zielpfad, Zielpfadmuster oder eindeutig benanntes Merge-Ziel.
- Solange exakte finale Dateinamen noch nicht feststehen, bleiben mindestens Artefaktklasse, Zielbereich im installierten Zielprojekt und spaetere Pruefbarkeit verbindlich.
- Doctor und Config-Check muessen diese Artefakte environment-spezifisch validieren koennen.

### Copilot Parity Contract

- Copilot wird im Rahmen des Agentensystems mit hoher funktionaler Paritaet zu Claude spezifiziert.
- Fuer jeden relevanten Baustein wird vertraglich festgehalten, ob Copilot `full` oder `approximate` erreicht.
- `full` ist nur zulaessig, wenn der Baustein denselben Kit-Zweck ohne Betreiber-Workaround als Pflichtmechanik erfuellt.
- `approximate` verlangt eine konkret benannte Ersatz- oder Annaeherungsmechanik.
- Fuer `hooks` ist `gap` in 015 ausgeschlossen; falls keine identische native Hook-Form existiert, ist eine native oder nativ integrierte, pruefbare Ersatzmechanik Pflicht.
- Bewusste Abweichungen von der Claude-Referenz muessen als solche markiert werden und duerfen nicht als implizite Gleichheit erscheinen.

### Environment Switch Contract

- Der Wechsel von `claude` zu `copilot` oder umgekehrt ist ein geplanter Migrationsfall.
- Upgrade oder Re-Init muessen hinzuzufuegende, zu ersetzende und konfliktbehaftete Agent-Artefakte sichtbar planen.
- Eigene Projektdateien und lokal geaenderte Kit-Dateien duerfen nicht still ueberschrieben werden.

## Copilot Parity Matrix

| Capability | Claude Reference | Copilot Expectation | Parity Level Requirement |
|---|---|---|---|
| `agents` | Benannte Claude-Agent-Artefakte | Benannte Copilot-Agent-Artefakte mit gleicher Rollenabdeckung | mindestens `approximate`, Ziel `full` |
| `skills` | Benannte Claude-Skill-Artefakte | Benannte Copilot-Skill-Artefakte oder gleichwertige Instruktionsbausteine | mindestens `approximate`, Ziel `full` |
| `hooks` | Native Claude-Hook-Anbindung | Native Hook-Anbindung oder explizit benannte native oder nativ integrierte Ersatzmechanik | `full` oder `approximate` |
| `instructions` | Claude-Instruktionsdateien | Copilot-Instruktionsdateien mit funktional entsprechender Steuerung | mindestens `approximate`, Ziel `full` |
| `settings` | Claude-settings-bezogene Schutz- und Integrationsregeln | Copilot-settings-bezogene Schutz- und Integrationsregeln mit gleicher Sicherheitssemantik | mindestens `approximate`, Ziel `full` |

## Constitution Notes

- **VI. Erprobtes uebernehmen**: Claude bleibt Referenz. Jede Copilot-Abweichung wird explizit als bewusste Designentscheidung klassifiziert.
- **VII. Testbar und ehrlich**: Diese Spec aendert die README nicht, verlangt fuer spaetere Umsetzung aber einen expliziten Statusmatrix-Checkpoint vor Abschluss der Implementierung.

## Test Expectations

- Contract-Tests fuer gueltige und ungueltige Agent-Umgebungswerte
- Tests fuer environment-spezifische verwaltete Agent-Artefaktsaetze
- Tests dafuer, dass Copilot-Projekte nicht an Claude-Pflichtartefakten scheitern
- Tests fuer die Copilot-Paritaetsmatrix je Baustein
- Tests fuer den konfliktbewussten Wechsel der Agent-Umgebung
