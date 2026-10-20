# Feature Specification: Init- und Upgrade-CLI

**Feature Branch**: `005-init-upgrade`

**Created**: 2026-10-20

**Status**: Draft

**Input**: ADR 0001 E3, E5, Constitution III und IV, `docs/architecture-vision.md` (Template + Init-CLI, Skill als Bedienoberfläche). Audit-Befunde zum alten `init-project.mjs`: stilles Überschreiben, keine Validierung, `baseUrl`-Platzhalter bleibt stehen.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Projekt sicher initialisieren (Priority: P1)

Der Betreiber ruft aus dem Kit-Repo auf: `uv run --project packages/engine sak init <ziel> --key ai-forge --name "AI-Forge"`. Er sieht zuerst einen Plan, welche Dateien neu entstehen, gemergt werden oder kollidieren. Erst mit `--apply` wird geschrieben.

**Independent Test**: Init in ein Fixture-Repo mit eigenen Agents, eigenem `settings.json`-Hook und spec-kit 0.12.16. Ergebnis:
- Keine bestehende Datei ist verändert, außer `settings.json`, und dort nur durch einen additiven Merge.
- `sak config check` meldet ok.
- `sak doctor` meldet ok.

**Acceptance Scenarios**:

1. **Given** ein ungültiger Schlüssel `../x y`, **When** `init` läuft, **Then** wird ohne jede Schreibaktion abgelehnt.
2. **Given** `.claude/agents/sak-builder.md` existiert schon mit anderem Inhalt, **When** `init --apply` läuft, **Then** bleibt die Datei unverändert, daneben entsteht `sak-builder.md.sak-new`, und der Bericht nennt den Konflikt.
3. **Given** das Ziel hat `defaultMode: bypassPermissions`, **When** `init` läuft, **Then** bleibt der Wert erhalten (Hoheit des Zielprojekts), und es kommt eine deutliche Warnung.
4. **Given** spec-kit fehlt im Ziel, **When** `init` läuft, **Then** wird mit dem genauen `specify init`-Befehl als Hinweis abgelehnt.

### User Story 2 – Kit-Updates nachrüsten (Priority: P1)

`sak upgrade <ziel>` (Plan, dann `--apply`) bringt Engine, Agents, Skills und Settings-Fragment auf die neue Kit-Version, ohne lokale Änderungen zu überschreiben.

**Acceptance Scenarios**:

1. **Given** `sak-code-reviewer.md` ist lokal unverändert (Hash = Lock), **When** `upgrade --apply` läuft, **Then** wird die Datei ersetzt, und der Lock-Hash wird aktualisiert.
2. **Given** die Datei ist lokal geändert, **When** `upgrade --apply` läuft, **Then** bleibt sie, `.sak-new` entsteht, und der Bericht zeigt einen Diff-Hinweis.
3. **Given** eine Kit-Datei entfällt in der neuen Version, **When** `upgrade --apply` läuft, **Then** wird sie gelöscht, wenn sie unverändert ist. Andernfalls bleibt sie und wird gemeldet.
4. **Given** `.spec-agent/config.yml`, **When** `upgrade` läuft, **Then** wird sie nie angefasst. Neue Config-Schlüssel werden nur gemeldet, mit Default-Werten.

### User Story 3 – Geführte Einrichtung per Skill (Priority: P2)

Im Kit-Repo führt der Skill `sak-init` durch die Einrichtung. Er fragt 5–8 Dinge: Zielpfad, Projektschlüssel, Name, Basis-Branch, UI ja/nein, Testbefehle, Dashboard-URL. Dann zeigt er den Plan, wendet ihn nach Bestätigung an, ruft `sak doctor` auf und erklärt die nächsten Schritte. Die Logik steckt vollständig im CLI.

### User Story 4 – Gesundheitscheck (Priority: P2)

`sak doctor` (im Ziel: `uv run --project .spec-agent/engine sak doctor`) prüft:
- Lock-Integrität
- Config gültig
- Engine lauffähig
- Hooks und Deny-Regeln vorhanden
- `.spec-agent/state/` gitignored
- spec-kit-Version unterstützt
- Dashboard erreichbar (nur wenn eine URL gesetzt ist; Timeout 3 s)

### Edge Cases

- **Ziel ist kein Git-Repo, oder der Arbeitsstand ist nicht sauber:** Ablehnung. `--allow-dirty` ist nur erlaubt, wenn keine geplante Aktion eine geänderte Datei berührt.
- **Init in ein bereits initialisiertes Projekt:** Ablehnung mit Verweis auf `upgrade`.
- **`settings.json` ist ungültiges JSON:** Ablehnung ohne Änderung.
- **Kit-Version im Ziel ist neuer als die des aufrufenden Kits** (Downgrade): Ablehnung.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: `sak init <ziel> --key --name [--base-branch main] [--dashboard-url] [--no-ui] [--test-fast …] [--test-full …] [--lint …] [--apply] [--allow-dirty]` MUSS ohne `--apply` nur den Plan ausgeben, als JSON plus lesbare Kurzfassung. Mit `--apply` setzt es genau diesen Plan um.
- **FR-002**: Init MUSS validieren:
  - Schlüssel nach Spec 001 FR-004
  - Name: 1–80 Zeichen, keine Steuerzeichen
  - Dashboard-URL: https, oder http für localhost
  - Ziel ist ein Git-Repo
  - Basis-Branch existiert
  - spec-kit vorhanden (`.specify/init-options.json`), Version ≥ 0.12.0
- **FR-003**: Init MUSS anlegen:
  - `.spec-agent/config.yml` aus der Vorlage (Spec 004), Platzhalter ersetzt, Werte aus den Optionen. Wird nur angelegt, wenn die Datei fehlt.
  - `.spec-agent/engine/`: Kopie von `packages/engine` ohne `tests/`, `.venv/`, Caches, inklusive `uv.lock`.
  - `.spec-agent/.gitignore`: `state/` und `dashboard.key`.
  - `.spec-agent/lock.json`
  - `.claude/agents/sak-*.md` und `.claude/skills/sak-pipeline/`
  - den Settings-Merge (FR-005)
- **FR-004**: Lockfile `sak.lock/1`: `kit_version`, `installed_at`, `upgraded_at`, `files{pfad: sha256}` für alle vom Kit verwalteten Dateien, ohne `config.yml`. Dazu `settings_fragment_hash`. Das Schema liegt in `packages/contracts/schema/lock.schema.json`.
- **FR-005**: Der Settings-Merge MUSS additiv sein:
  - Hook-Einträge des Kits werden ergänzt, wenn noch kein Eintrag mit `.spec-agent/engine` im Befehl existiert.
  - `permissions.allow` und `permissions.deny` werden vereinigt.
  - Bestehende Einträge und `defaultMode` bleiben unverändert. Bei `bypassPermissions` gibt es eine Warnung.
  - Ohne Datei wird sie aus dem Fragment angelegt.
  - Formatierung: 2 Spaces, Reihenfolge der Schlüssel bleibt erhalten.
- **FR-006**: Konflikte, also existierende Dateien mit anderem Inhalt und nicht im Lock, MÜSSEN als `<datei>.sak-new` danebengelegt und berichtet werden. Überschrieben wird nie.
- **FR-007**: `sak upgrade <ziel> [--apply]` MUSS die Regeln aus US2 umsetzen. Danach meldet es neue Config-Schlüssel (Vergleich wirksame Defaults ↔ Datei) und führt `uv sync` im Engine-Ordner aus.
- **FR-008**: `sak doctor` MUSS die Prüfungen aus US4 als Liste `{check, ok, detail}` ausgeben. Exit 1, wenn eine Pflichtprüfung fehlschlägt.
- **FR-009**: Nach `--apply` MUSS `uv sync --project .spec-agent/engine` laufen, gefolgt von `config check`. Init und upgrade committen nie. Der Bericht schlägt einen Commit-Befehl vor.
- **FR-010**: Das alte Gerüst MUSS entfernt werden:
  - `scripts/init-project.mjs`
  - `packages/agent-blueprint/templates/root/`
  - `packages/agent-blueprint/AGENTS.md`, das neu geschrieben wird

  Der Skill `sak-init` liegt im Kit-Repo unter `.claude/skills/sak-init/SKILL.md`.

### Key Entities

Installationsplan (Aktionen: `create`, `merge`, `replace`, `delete`, `conflict`, `skip`), Lockfile.

## Success Criteria *(mandatory)*

- **SC-001**: Init, Upgrade und erneutes Init sind idempotent. Ein zweiter `upgrade --apply` ohne Kit-Änderung ergibt einen leeren Plan.
- **SC-002**: Nach dem Init in das Fixture-Repo (AI-Forge-ähnlich, mit eigenen Agents und Hooks) ist `git diff` auf bestehende Dateien leer, mit Ausnahme des additiven Merges in `settings.json`.
- **SC-003**: Smoke-Test: Init, `doctor`, eine Kit-Datei lokal ändern, Kit-Version erhöhen, Upgrade. Der Konflikt wird korrekt erkannt. Läuft in CI auf Windows und Linux.

## Assumptions

- Der Init läuft aus einem Checkout des Kit-Repos. Eine Verteilung per `uvx --from git+…` ist später möglich, weil derselbe Befehl gilt, setzt aber ein Remote voraus.
- Die Testbefehle aus den Optionen werden auch in `permissions.allow` des Ziels eingetragen (Spec 003 FR-015).
