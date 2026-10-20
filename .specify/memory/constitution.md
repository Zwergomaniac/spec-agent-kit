# spec-agent-kit Constitution

## Core Principles

### I. Contracts zuerst

- `packages/contracts` (JSON-Schema) ist die einzige Quelle der Wahrheit für Ereignisse, Board-Dokument,
  Projektregistrierung und Statuswerte. Daraus werden TS/Zod-Typen und Python-Validierung abgeleitet,
  nie umgekehrt.
- Es gelten ausschließlich die Maschinenwerte des Vokabulars (Spec 001). Ein neuer Wert MUSS zuerst
  im Vokabular und im Schema stehen, bevor Engine, Collector oder Dashboard ihn nutzen.
- Vertragsänderungen MÜSSEN versioniert werden (Regeln in Spec 002). Ein Breaking Change braucht eine
  neue Hauptversion.

**Begründung:** Engine, Collector und Dashboard sind in verschiedenen Sprachen geschrieben und werden
getrennt ausgerollt. Ohne führenden Vertrag driften sie auseinander.

### II. Nur Metadaten

- An das Dashboard und in Ereignisse gelangen nur Metadaten: Zustände, Zeiten, Zähler, Namen,
  Pfade auf Spec-Ebene.
- Code, Diffs, Prompts, Agenten-Antworttexte, Befund-Inhalte, Zugangsdaten und Secrets verlassen
  das Zielprojekt NIE.
- Das Dashboard MUSS unbekannte oder zu große Felder ablehnen statt sie zu speichern.

**Begründung:** Das Dashboard bündelt mehrere Projekte. Ein Leck dort betrifft alle.

### III. Hoheit des Zielprojekts

- Init und Upgrade überschreiben NIE still. Geänderte Dateien werden erkannt (Lockfile mit Hashes)
  und nur nach Bestätigung ersetzt.
- Projektspezifische Konfiguration, eigene Agents, Skills und Hooks des Zielprojekts bleiben unangetastet.
- Eingaben (Projektschlüssel, Pfade, URLs) werden validiert, bevor etwas geschrieben wird.
- Jede Aktion des Kits im Zielprojekt ist wiederholbar (idempotent) und nachvollziehbar.

**Begründung:** Zielprojekte wie AI-Forge haben bereits eigene Agents und Hooks. Ein Framework, das
Projektdateien zerstört, wird nicht eingesetzt.

### IV. Sicherer Default

- Templates setzen NIE `bypassPermissions`. Der Default ist ein restriktiver Modus mit Allowlist für
  Pipeline-Befehle und Deny-Regeln für Push, Deploy, SSH und `.env`.
- Geschützte Pfade (Pipeline-Dateien, Agents, Settings, Constitution) ändert nur der Betreiber.
  Die Engine erzwingt das mechanisch.
- Diese Freigaben trifft immer ein Mensch:
  - Start jeder Umsetzung („umsetzen“ je Spec)
  - Release eskalierter Läufe
  - Deploy
- Jeder Schreibzugriff auf das Dashboard ist authentifiziert (Schlüssel je Projekt), validiert und
  größenbegrenzt. Lesen erfordert eine Admin-Anmeldung.

**Begründung:** Agenten handeln autonom. Schäden durch zu offene Defaults lassen sich später kaum
wieder einfangen.

### V. Planen und Umsetzen getrennt

- Die Hauptsitzung plant: Specs, Pläne, ADRs, Briefings. Umsetzung erfolgt durch Subagents.
- Umsetzung beginnt erst nach ausdrücklichem „umsetzen“ des Betreibers je Spec.
- Feste Spec-Kette: specify → clarify → plan → tasks → implement → analyze.
- Ergebnisse von Subagents werden vor der Meldung „erledigt“ von der Hauptsitzung geprüft (Diff, Tests).

**Begründung:** Die Trennung spiegelt das Orchestrator-Prinzip der Pipeline und schützt den Kontext
der planenden Sitzung.

### VI. Erprobtes übernehmen

- Die ImmoAgent-Implementierung (Specs 092, 093) ist die Referenz. Sie wird nur gelesen.
- Bewährte Mechanik wird generalisiert übernommen, nicht neu erfunden: Zustandsmaschine, Guard,
  Snapshot, Urteils-Parser, Hook-Events, Board-Ableitung.
- Jede bewusste Abweichung von der Referenz MUSS im Plan der Spec mit Grund dokumentiert sein.

**Begründung:** Der Pilot in ImmoAgent hat die Mechanik unter realen Bedingungen bestätigt.
Neuschreiben kostet Zeit und bringt neue Fehler.

### VII. Testbar und ehrlich

- Jede Komponente hat automatisierte Tests: Schema-Tests der Contracts, Unit-Tests der Engine,
  Smoke-Test für Init und Upgrade, API-Vertragstests. CI MUSS sie bei jeder Änderung ausführen.
- Platzhalter-Skripte (`echo`) gelten nicht als Test.
- Die Statusmatrix im README (Konzept / Mock / implementiert) wird mit jeder Spec aktualisiert.
  Doku DARF nichts behaupten, was nicht existiert.

**Begründung:** Das Audit zeigte, dass Doku über dem tatsächlichen Stand das Hauptrisiko war.

### VIII. Generisch mit Erweiterungspunkten

- Im Kern stehen keine Projekt-Hardcodes: keine Pfade wie `src/<projekt>/`, keine Stack-Befehle,
  keine projektspezifischen Prüfthemen. Alles davon steht in der Projektkonfiguration (Spec 004).
- Kern und Plugins sind getrennt (ADR 0001 E6). Optionale Teile wie graphify, impeccable oder
  Queue/Backlog sind nie Voraussetzung für den Kern.
- Die Engine läuft plattformneutral über `uv run`. Pfade und Ausgabe-Encoding sind auf Windows,
  Linux und macOS gleichwertig, UTF-8 wird erzwungen.
- Entscheidungen DÜRFEN den späteren Parallelbetrieb (Worktrees, mehrere Läufe) nicht verbauen.

**Begründung:** Das Kit muss in Projekten mit und ohne UI, mit verschiedenen Stacks und auf
verschiedenen Rechnern funktionieren.

## Technische Leitplanken

- **Engine und Collector im Zielprojekt:** Python ≥ 3.11, gestartet über `uv run`. Keine
  hart verdrahteten Interpreter-Pfade.
- **Dashboard:** TypeScript mit Hono, React/Vite, Tailwind/shadcn, SQLite (WAL) und Zod. Ein
  Container hinter dem extern betriebenen Caddy. Caddy wird in diesem Repo nicht verwaltet.
- **Dashboard-UI:**
  - Portfolio ist die Startansicht.
  - Deep Links auf Projekt-, Tab- und Lauf-Ebene sind Pflicht.
  - Maschinenwerte sind englisch, Labels per Locale (Default `de`).
- **spec-kit:** Upstream-Abhängigkeit mit dokumentierter Mindestversion. Das Kit liefert nur die
  Pipeline-Schicht.
- **Monorepo:** pnpm-Workspace für TS-Pakete, uv-Projekt für Python-Pakete. Blueprint und Dashboard
  werden gemeinsam versioniert.

## Arbeitsablauf und Qualitäts-Gates

- **Gate 1 (nach `/speckit-plan`):** Der Plan prüft jedes Prinzip I–VIII. Verstöße stehen begründet
  in „Complexity Tracking“.
- **Gate 2 (vor der Umsetzung):** „umsetzen“ des Betreibers liegt vor, Checklisten sind abgeschlossen.
- **Gate 3 (nach der Umsetzung):**
  - Tests grün in CI
  - `/speckit-analyze` ohne CRITICAL-Befunde
  - README-Statusmatrix aktualisiert
- **Branches und Commits:**
  - Ein Branch je Spec (`NNN-slug`).
  - Commits nur auf Anweisung, nie Push ohne Freigabe.
  - Deploy-Marker im Format `deploy(NNN): …`, `verified(NNN): …`.

## Governance

- Diese Constitution hat Vorrang vor anderen Arbeitsanweisungen im Repo. CLAUDE.md und AGENTS.md
  dürfen ihr nicht widersprechen.
- **Änderungen:** nur durch den Betreiber, dokumentiert als Amendment mit Sync-Impact-Report.
  Bei einer grundlegenden Entscheidung zusätzlich ein ADR unter `docs/adr/`.
- **Versionierung (SemVer):**
  - MAJOR: Prinzip entfernt oder umdefiniert
  - MINOR: Prinzip oder Abschnitt neu oder wesentlich erweitert
  - PATCH: Klarstellung
- Jeder Plan und jedes Review prüft die Einhaltung. Verstöße ohne Begründung blockieren die Umsetzung.

**Version**: 1.0.0 | **Ratified**: 2026-10-20 | **Last Amended**: 2026-10-20
