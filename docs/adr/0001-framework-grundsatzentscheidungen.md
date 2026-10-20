# ADR 0001: Grundsatzentscheidungen für die Framework-Extraktion

- **Status:** angenommen
- **Datum:** 2026-10-20
- **Entschieden von:** Betreiber
- **Kontext-Quellen:** Audit des Gerüsts (2026-10-20), Bestandsaufnahme ImmoAgent (Specs 092 Dev-Board, 093 Agenten-Pipeline), `docs/architecture-vision.md`

## Kontext

spec-agent-kit soll das in ImmoAgent entstandene System als wiederverwendbares, in anderen Projekten initialisierbares Framework bereitstellen. Gemeint sind die Spec-getriebene Agenten-Pipeline und das Dev-Board.

Das Audit des ersten Gerüsts ergab Folgendes: Die Doku beschreibt einen Kern, der im Repo nicht existiert. Contracts, Status-Begriffe und Datenfluss weichen von dem ab, was ImmoAgent tatsächlich tut. Die Referenz-Implementierung liegt erprobt in ImmoAgent:

- `pipeline.py`: Zustandsmaschine, Guard, Snapshot, Urteils-Parser, Hook-Events
- `dev_board.py`: Board aus Dateien und Git
- drei Rollen-Agents

Sie ist dort aber an Windows, venv-Pfade, deutsche Strings und Projektspezifika gekoppelt.

## Entscheidungen

### E1 Laufzeiten
- **Engine im Zielprojekt: Python, gestartet über `uv run`.** Gemeint sind Pipeline, Queue und Feature-Status. Der erprobte ImmoAgent-Code wird generalisiert übernommen, nicht neu geschrieben. Es gibt keine fest verdrahteten Pfade wie `.venv/Scripts/python.exe`.
- **Dashboard: TypeScript.** Stack: Hono, React mit Vite, Tailwind mit shadcn/ui, SQLite (WAL) und Zod. Ein Container liefert API und gebaute UI aus.
- **Contracts sind sprachneutral und als JSON-Schema definiert** (`packages/contracts`). Daraus entstehen TS/Zod-Typen für das Dashboard und die Validierung in Python für Engine und Collector. Das Schema ist die einzige Quelle der Wahrheit.

### E2 Datenfluss: hybrid
- Ein **lokaler Collector pro Projekt** erzeugt das Board-Dokument aus Spec-Dateien, Git und `events.jsonl`. Das ist das Prinzip von `dev_board.py`, inklusive „keine zweite Status-Quelle“.
- Der Collector **pusht** Snapshot und Events an das zentrale Dashboard. Das Pushen ist ausfallsicher: kurzer Timeout, lokale Warteschlange, die Pipeline wird nie blockiert.
- Das lokale Board funktioniert auch ohne zentrales Dashboard.
- Das zentrale Dashboard speichert **nur Metadaten**. Code, Prompts, Diffs, Tokens und Secrets speichert es nicht.

### E3 speckit
- github spec-kit ist eine **Upstream-Abhängigkeit**. spec-agent-kit liefert nur die Pipeline-Schicht darauf: Agents, Pipeline-Config, Hooks, Collector und Skills.
- Zielprojekte können unterschiedliche spec-kit-Versionen haben, zum Beispiel ImmoAgent 1.0.13 und AI-Forge 0.12.16. Init und Upgrade erkennen die Version und legen eine Mindestversion fest.

### E4 Sprache
- Maschinenwerte (Keys, Status, Urteile, Event-Typen) sind **englisch**.
- Labels, Agent-Prompts und Berichte sind per Locale steuerbar, **Default `de`**.
- Für die spätere Rückmigration von ImmoAgent gibt es eine Mapping-Tabelle von DE nach EN.

### E5 Rollout: Init- und Upgrade-CLI
- Templates und Init-CLI. Ein Agent-Skill ist nur die Bedienoberfläche über dem CLI.
- Im Zielprojekt liegt ein Lockfile mit Kit-Version und Datei-Hashes.
- Upgrade aktualisiert unveränderte Dateien, zeigt bei lokal geänderten Dateien einen Diff und fasst projektspezifische Config nie an.
- Kein stilles Überschreiben. Projekt-Keys werden validiert.

### E6 Kern oder Plugin
- **Kern:**
  - Pipeline-Grundlogik
  - Rollen- und Freigabemechanik
  - Event- und Statusmodell
  - Dashboard-Anbindung (Collector, Push)
  - Commit-Marker `deploy(NNN)` / `verified(NNN)`
- **Optional, als Plugins:**
  - graphify
  - impeccable
  - Queue- und Backlog-Dateien (`queue.yml`, `blockers.yml`, `abarbeitungsplan.md`, `backlog.md`, `deferred-decisions.md`)
  - projektspezifische Skills

### E7 Guardrails
- **Restriktiver Default.** `bypassPermissions` ist nie der Default in Templates.
- Grundmodus mit Allowlist für Pipeline-Befehle und Deny-Regeln für Push, Deploy, SSH und `.env`.
- Geschützte Pfade (Pipeline-Dateien, Agents, Settings, Constitution) ändert nur der Betreiber. Das erzwingt `guard` mechanisch.
- Freigaben bleiben beim Menschen: „umsetzen“ je Spec, Release bei Eskalation, Deploy.

### E8 Rollen
- **v1 liefert:** `builder`, `code-reviewer`, `ui-reviewer`. Der UI-Prüfer ist abschaltbar, etwa für Projekte ohne UI wie AI-Forge.
- Rollen und Stationen sind eine **konfigurierbare Liste**, nicht fest kodiert.
- `security` und `docs` sind vorgesehene, optionale Stationen.
- `integrator` kommt mit dem Parallelbetrieb.

### E9 Parallelbetrieb
- **v1:** höchstens ein aktiver Lauf pro Projekt, mehrere Projekte parallel.
- Ab v1 gibt es eine **eigene Run-ID**: Spec plus Zeitstempel bzw. ULID, statt nur des Spec-Namens. Die Run-Historie wird nicht überschrieben.
- Das Modell darf Worktree-Parallelbetrieb nicht verbauen. Herkunftsfelder (Maschine, Worktree, Branch) sind im Vertrag optional vorgesehen.

### E10 Dashboard-Betrieb
- **Eigener Container auf dem VPS** hinter dem extern betriebenen edge-caddy. Es wird nicht in eine App eingebettet.
- **Auth:**
  - Lesen: ein Admin-Passwort mit Session-Cookie.
  - Schreiben (Ingest): ein API-Key pro Projekt, mit Schema-Validierung, Größenlimit und Retention für Events (Startwert 30 Tage).
- UI: Portfolio als Startansicht, Deep Links auf Projekt-, Tab- und Run-Ebene.
- Cloud-Sitzungen werden mitgedacht (HTTPS-Ingest), sind aber keine Voraussetzung für v1.

### E11 Pilot und Referenz
- **Erster Pilot:** AI-Forge (Python, VPS, spec-kit 0.12.16, keine Web-UI, eigene Agents und Hooks vorhanden).
- **ImmoAgent** bleibt vorerst Ursprung, Referenz und Testbett und wird nur gelesen. Die Rückmigration auf das Framework kommt später als eigene Spec.

### E12 Arbeitsweise im Kit
- spec-kit wird im Kit selbst genutzt (Dogfooding). Specs liegen unter `specs/NNN-*`.
- Die Hauptsitzung plant. Umsetzung durch Subagents, erst nach ausdrücklichem „umsetzen“ je Spec.

## Spec-Reihenfolge

| # | Spec |
|---|---|
| 001 | Domänenmodell und Status-Begriffe |
| 002 | Contracts: Event- und Board-Vertrag v1 |
| 003 | Pipeline-Engine (generalisiert) |
| 004 | Konfigurationsgrenze |
| 005 | Init- und Upgrade-CLI |
| 006 | Collector und Ingest |
| 007 | Dashboard v1 |
| 008 | Pilot AI-Forge |

Danach jeweils als eigene Spec: Plugins, Parallelbetrieb mit Worktrees und Integrator, Rückmigration von ImmoAgent.

## Folgen

- Das bestehende Gerüst (`EventEnvelope`, Mock-API, `routes.ts`, Beispiel-Events) ist **vorläufig**. Es wird durch die Specs 001 und 002 ersetzt, nicht erweitert.
- Die in `docs/architecture-vision.md` empfohlene Formulierung „TypeScript überall“ gilt nur für das Dashboard. Für die Engine gilt E1.
- Das Mixed Repo bleibt. Den Vertrag zwischen Engine und Dashboard bildet das versionierte JSON-Schema.
