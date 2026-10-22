# Data Model: Agent-System-Abstraktion fuer Claude und GitHub Copilot

## Entities

### Agent Environment

- **Purpose**: Beschreibt die eine Agent-Umgebung, die das Kit in einem Zielprojekt aktiv verwaltet.
- **Fields**:
  - `key`: stabiler Maschinenwert, `claude` oder `copilot`
  - `display_name`: menschenlesbarer Name
  - `adapter_key`: Referenz auf den zugehoerigen Agent-System-Adapter
  - `supports_native_hooks`: Kennzeichen, ob native Hook-Mechanik verfuegbar ist
  - `notes`: erklaerende Hinweise zu environment-spezifischen Besonderheiten
- **Relationships**:
  - Ein Zielprojekt referenziert genau eine aktive Agent-Umgebung.
  - Eine Agent-Umgebung bestimmt den verwalteten Agent-Artefaktsatz und die Validierungslogik.

### Agent System Adapter

- **Purpose**: Ordnet die agentneutralen Konzepte des Kits der konkreten Agent-Umgebung zu.
- **Fields**:
  - `environment`: Referenz auf die Agent-Umgebung
  - `managed_artifacts`: Referenz auf den verwalteten Agent-Artefaktsatz
  - `validation_rules`: Menge der environment-spezifischen Pflicht- und Warnregeln
  - `parity_capabilities`: Menge der Copilot-Paritaetsbausteine, soweit relevant
  - `switch_rules`: Regeln fuer den environment-Wechsel
- **Relationships**:
  - Genau ein Adapter pro unterstuetzter Agent-Umgebung.
  - Wird von Init, Upgrade, Config-Check und Doctor genutzt.

### Managed Agent Artifact Set

- **Purpose**: Beschreibt die vom Kit verwalteten Agent-System-Artefakte einer Agent-Umgebung.
- **Fields**:
  - `agents`: benannte Agent-Dateien oder Agent-Rollenartefakte
  - `skills`: benannte Skill-Artefakte
  - `hooks`: benannte Hook-Artefakte oder Hook-Ersatzartefakte
  - `instructions`: benannte Instruktionsdateien oder Instruktionsfragmente
  - `settings`: benannte settings-bezogene Artefakte oder Merge-Ziele
  - `managed_paths`: alle vom Kit dafuer verwalteten Pfade
- **Relationships**:
  - Gehoert genau zu einer Agent-Umgebung.
  - Wird in Lock-, Plan- und Doctor-Logik referenziert.

### Parity Capability

- **Purpose**: Beschreibt fuer einen relevanten Agent-System-Baustein die Copilot-Paritaet gegenueber Claude.
- **Fields**:
  - `capability_key`: stabiler Name des Bausteins, z. B. `agents`, `skills`, `hooks`, `instructions`, `settings`
  - `parity_level`: `full` oder `approximate`
  - `claude_mechanism`: kurze Beschreibung der Claude-Referenz
  - `copilot_mechanism`: kurze Beschreibung der Copilot-Abbildung
  - `verification_expectation`: was spaeter durch Tests oder Doctor pruefbar sein muss
  - `notes`: erklaerende Hinweise
- **Relationships**:
  - Wird im Copilot-Adapter gefuehrt.
  - Dient Spec, Quickstart und spaeteren Tests als Pruefraster.

### Environment Switch Plan

- **Purpose**: Beschreibt den geplanten Wechsel einer aktiv verwalteten Agent-Umgebung in einem Zielprojekt.
- **Fields**:
  - `from_environment`: bisher aktiv verwaltete Agent-Umgebung
  - `to_environment`: neu gewaehlt Agent-Umgebung
  - `artifacts_to_add`: neue verwaltete Agent-Artefakte
  - `artifacts_to_replace`: zu ersetzende verwaltete Agent-Artefakte
  - `conflicts`: lokal geaenderte oder kollidierende Pfade
  - `operator_actions`: notwendige Betreiberentscheidungen
- **Relationships**:
  - Wird von Plan- und Upgrade-Verhalten genutzt.

### Project Agent Configuration

- **Purpose**: Beschreibt den agentbezogenen Teil der Projektkonfiguration.
- **Fields**:
  - `environment`: die aktiv verwaltete Agent-Umgebung
  - `agent_settings`: environment-spezifische agentbezogene Settings
  - `custom_project_artifacts_present`: Kennzeichen fuer projektseitige eigene Agents, Skills oder Hooks
  - `validation_mode`: Ergebnislogik fuer Pflicht-, Warn- und Hinweispruefungen
- **Relationships**:
  - Referenziert genau eine Agent-Umgebung.
  - Wird von Config-Check und Doctor ausgewertet.

## Validation Rules

- Genau eine aktive Agent-Umgebung ist erlaubt.
- Jede unterstuetzte Agent-Umgebung muss einen definierten Agent-System-Adapter besitzen.
- Fuer jede Agent-Umgebung muessen Agents, Skills, Hooks oder Hook-Ersatz, Instruktionen und settings-bezogene Artefakte konkret benannt sein.
- Copilot darf fuer keinen Pflichtbaustein implizit auf Claude-Artefakte verweisen.
- Paritaetsbausteine fuer Copilot muessen je Baustein einen `parity_level` und eine pruefbare Erwartung besitzen.
- Der Hook-Baustein fuer Copilot muss immer eine vorhandene native oder nativ integrierte Mechanik beschreiben; `approximate` ohne konkrete Ersatzmechanik ist ungueltig.
- Ein Environment-Wechsel muss als geplanter Konfliktfall beschrieben sein; stille Ersetzungen sind unzulaessig.
