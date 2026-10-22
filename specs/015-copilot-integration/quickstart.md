# Quickstart: Agent-System-Abstraktion fuer Claude und GitHub Copilot

## Ziel

Diese Validierung zeigt, dass das Kit im Zielprojekt einen vertraglich klaren Agent-Zustand fuer `claude` und `copilot` herstellen kann, ohne in einen allgemeinen Repo-Multi-Integrationsscope auszuweiten. Geprueft werden ausschliesslich Agents, Skills, Hooks, Instruktionen und agentbezogene Settings.

## Voraussetzungen

- Workspace-Abhaengigkeiten installiert (`pnpm install`, `uv sync --project packages/engine`)
- Ein sauberes Testprojekt fuer `claude`
- Ein sauberes Testprojekt fuer `copilot`
- Ein bestehendes Claude-Testprojekt fuer den Environment-Wechsel oder Upgrade-Fall
- Zugriff auf die CLI im Repo: `uv run --project packages/engine sak`

## Szenario 1: Claude bleibt unveraendert funktionsfaehig

1. Ein Testprojekt fuer die Agent-Umgebung `claude` planen und anwenden.
2. `sak config check` ausfuehren.
3. `sak doctor` ausfuehren.
4. Erwartung:
   - Claude-Agent-Artefakte sind vorhanden und werden validiert.
   - Bestehende Claude-Annahmen funktionieren weiter.
   - Keine Copilot-Artefakte werden als Pflicht verlangt.

## Szenario 2: Copilot-Projekt mit eigenem Agent-Artefaktsatz initialisieren

1. Ein sauberes Testprojekt fuer `copilot` planen.
2. Den Plan anwenden.
3. `sak config check` und `sak doctor` ausfuehren.
4. Erwartung:
    - Copilot-spezifische Agents, Skills, Hooks oder Hook-Ersatzartefakte, Instruktionen und Settings-Artefakte werden an den vorgesehenen Zielstellen des Zielprojekts installiert.
   - Claude-Artefakte sind keine Copilot-Pflicht.
   - Der Agent-System-Vertrag ist fuer Copilot konkret benannt und pruefbar.

## Szenario 3: Copilot-Paritaetsmatrix pruefen

1. Die in `spec.md` oder `contracts/integration-contract.md` definierte Paritaetsmatrix fuer Copilot durchgehen.
2. Fuer jeden Baustein `agents`, `skills`, `hooks`, `instructions` und `settings` die erwartete Stufe pruefen.
3. Erwartung:
    - Jeder Baustein ist als `full` oder `approximate` eingeordnet.
    - Bei `approximate` ist die Ersatzmechanik konkret beschrieben.
    - Fuer `hooks` beschreibt `approximate` eine vorhandene native oder nativ integrierte, pruefbare Mechanik und nicht das Fehlen von Hooks.

## Szenario 4: Environment-spezifische Validierung pruefen

1. `sak config check` und `sak doctor` in einem Claude-Projekt ausfuehren.
2. Dieselben Befehle in einem Copilot-Projekt ausfuehren.
3. Erwartung:
   - Claude prueft nur Claude-relevante Agent-Artefakte.
   - Copilot prueft nur Copilot-relevante Agent-Artefakte.
    - Pflicht, Warnung und dokumentierte Approximation sind sauber getrennt.

## Szenario 5: Wechsel der Agent-Umgebung konfliktbewusst planen

1. Von einem bestehenden Claude-Projekt ausgehen.
2. Einen Wechsel auf `copilot` planen.
3. Erwartung:
   - Der Plan listet hinzuzufuegende, zu ersetzende und konfliktbehaftete Agent-Artefakte.
   - Keine Datei wird still ueberschrieben.
   - Eigene Projekt-Artefakte bleiben erhalten oder werden explizit als Konflikt ausgewiesen.
