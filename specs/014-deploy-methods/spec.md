# Feature Specification: Deploy-Wege (GitHub-Workflow und lokal)

**Feature Branch**: `014-deploy-methods`

**Created**: 2026-10-22

**Status**: Planned

**Input**: Betreiber 2026-10-22. Er will ohne PC deployen können (GitHub Actions mit Freigabe, siehe `docs/howto/github-actions-deploy.md`). Gleichzeitig soll das lokale Deploy per SSH weiter möglich sein („wer weiß, wie lange GitHub Actions gratis sind“). Lücken im Skill `sak-pipeline` (0.4.0):
- Er setzt immer selbst den Marker `deploy(NNN)`. Beim Workflow wäre der Marker doppelt.
- Er ersetzt `{spec}` nicht dokumentiert.
- Er nimmt an, ein Deploy sei sofort fertig. Ein Workflow ist dagegen nur angestoßen und wartet auf die Freigabe auf GitHub.

## Clarifications

### Session 2026-10-22

- Q: Ein oder mehrere Deploy-Wege? → A: Mehrere benannte Wege je Projekt, mit Default. Der Betreiber wählt per Wortlaut („deployen“ = Default, „deployen lokal“ / „deployen github“ = benannter Weg).
- Q: Rückwärtskompatibilität? → A: `deploy.command` bleibt gültig und entspricht einem einzigen Weg `default` mit `marker: agent`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Zwei Wege, ein Default (Priority: P1)

**Acceptance Scenarios**:
1. **Given** die Config hat `deploy.methods.github` (Workflow, `marker: workflow`) und `deploy.methods.local` (`bash deploy/deploy-vps.sh`, `marker: agent`, `local_only: true`) sowie `deploy.default: github`, **When** der Betreiber „deployen“ sagt, **Then** stößt der Orchestrator den Workflow an, setzt KEINEN Marker und berichtet: „Deploy angestoßen, wartet auf deine Freigabe auf GitHub“.
2. **Given** dieselbe Config, **When** der Betreiber „deployen lokal“ sagt, **Then** führt der Orchestrator den lokalen Befehl aus und setzt nach Erfolg selbst den Marker `deploy(NNN)` (bei `autonomy.push: after_merge` danach `sak run push`).
3. **Given** eine Cloud-Sitzung, **When** ein Weg mit `local_only: true` gewählt wird, **Then** lehnt der Orchestrator ab und nennt den Grund („lokales Deploy braucht SSH vom Rechner des Betreibers“). Er schlägt den Default bzw. den Workflow vor.

### User Story 2 – Platzhalter und Prüfbarkeit (Priority: P1)

- `{spec}` im Befehl wird durch die Spec-Nummer(n) ersetzt (z. B. `084` oder `084,085`).
- `sak config show` listet die Wege. `sak deploy plan [--method <name>] <run|spec>` gibt den aufgelösten Befehl, den Weg, den Marker-Modus und ob der Weg in dieser Umgebung erlaubt ist, als JSON aus, ohne etwas auszuführen. Der Skill nutzt diese Ausgabe, statt selbst zu ersetzen.

## Requirements *(mandatory)*

- **FR-001**: Contract-Erweiterung `sak.config/1`, rückwärtskompatibel:
  - `deploy.methods: {<name>: {command, marker: agent|workflow (Default agent), local_only: bool (Default false)}}`
  - `deploy.default: <name>`
  - Das bestehende `deploy.command` wird intern zu `methods.default` mit `marker: agent`.
  - `deploy.command` und `deploy.methods` gleichzeitig sind ungültig.
- **FR-002**: `sak deploy plan` nach US2. Die Umgebungserkennung nutzt dieselbe Heuristik wie Spec 013 (Proxy-Variablen) und zusätzlich die Umgebungsvariable `SAK_ENVIRONMENT=cloud|local` als explizite Übersteuerung.
- **FR-003**: Skill `sak-pipeline`, Abschnitt Deploy:
  - Wahl des Wegs nach Wortlaut des Betreibers oder Default.
  - `sak deploy plan` aufrufen und Ablehnungen beachten.
  - Befehl ausführen.
  - Bei `marker: agent` den Marker selbst setzen und ggf. pushen, bei `marker: workflow` keinen Marker setzen und „angestoßen, wartet auf Freigabe“ berichten.
  - Die bestehenden Regeln bleiben: nur nach ausdrücklichem „deployen“, nur bei `autonomy.deploy: after_approval`, nie durch Subagents.
- **FR-004**: Vorlage `config.yml` kommentiert beide Wege. Beispiel ImmoAgent: `github` (Default) und `local`. Die Doku `docs/howto/github-actions-deploy.md`, Schritt 6, zeigt die neue Form.
- **FR-005**: Kit-Version 0.5.0.

## Success Criteria *(mandatory)*

- **SC-001**: Tests für `deploy plan`: Default, benannter Weg, unbekannter Weg, `local_only` in Cloud (abgelehnt) und lokal (erlaubt), `{spec}`-Ersetzung mit einer und mehreren Specs, Altform `deploy.command`.
- **SC-002**: Ungültige Kombinationen in der Config werden von `config check` erkannt.
