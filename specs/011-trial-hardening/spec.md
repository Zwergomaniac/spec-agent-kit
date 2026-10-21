# Feature Specification: Robustheit aus dem ImmoAgent-Trial

**Feature Branch**: `011-trial-hardening`

**Created**: 2026-10-21

**Status**: Implemented (Kit 0.2.0)

**Input**: Bericht „sak-Trial ImmoAgent“ vom 2026-10-20/21: Kit-Commit `4d78cb3` von GitHub, ImmoAgent-Branch `sak-trial`, Nur-Prüfungs-Lauf `084-20261020-221040`. Die Befunde zur Board-Ableitung (Befund 5) stehen in Spec 010 US6.

## User Scenarios & Testing *(mandatory)*

### User Story 1 – Hooks funktionieren ohne uv im PATH (Priority: P1) — Hotfix vorgezogen

Befund 1 (hoch): Die Hooks riefen `uv` direkt auf. War uv nicht im PATH der Claude-Code-Sitzung, scheiterten sie still (`|| true`), und es entstanden keine Stations-Events. `doctor` meldete trotzdem „Hooks vorhanden“.

**Acceptance**: Die Hooks laufen über den Starter `.spec-agent/sak`, der uv selbst sucht. Bei `upgrade` werden vorhandene Kit-Hooks ersetzt statt doppelt ergänzt. `doctor` führt eine echte Hook-Probe aus (Starter mit minimalem PATH und Beispiel-Payload) und meldet Fehler als nicht ok.

### User Story 2 – Prüfer-Artefakte lösen keine falsche Integritäts-Eskalation aus (Priority: P1)

Befund 2 (hoch): Playwright schreibt `test-results/` ins Projektverzeichnis. Dadurch eskaliert jeder UI-Prüflauf mit `review_integrity`.

**Acceptance**: Bekannte Test-Artefakte werden entweder nach `.spec-agent/state/runs/<id>/` umgelenkt (Prüfer-Anweisung und UI-Befehl) oder per vorgeschlagenem `clean_ignore` toleriert. `init` schlägt passende Einträge vor, wenn es Playwright im Projekt erkennt. Ein echter Eingriff eines Prüfers in Quelldateien eskaliert weiterhin.

### User Story 3 – Läufe in Worktrees (Priority: P2)

Befund 3 (mittel): Die Hooks schreiben immer nach `$CLAUDE_PROJECT_DIR`. Läufe in einem Worktree bekommen dadurch keine Stations-Events, und Dashboard-URL und Schlüssel fehlen dort.

**Acceptance**: Entweder lösen die Hooks den Ort des aktiven Laufs auf (Worktree des Laufs), und Push-Einstellungen bzw. Schlüssel werden aus dem Haupt-Checkout geerbt. Oder die Grenze ist klar dokumentiert und `preflight` warnt. Die Entscheidung fällt bei der Klärung, mit Blick auf den Parallelbetrieb (Constitution VIII).

### User Story 4 – Testbefehle passen zum Projekt (Priority: P2)

Befund 4 (mittel): `uv run pytest` scheitert, wenn pytest in `optional-dependencies` (Extra `dev`) statt in `dependency-groups` steht.

**Acceptance**: `init` liest `pyproject.toml` und schlägt `--extra …` bzw. `--group …` vor. `doctor` führt die Testbefehle probeweise aus (z. B. `pytest --collect-only -q`, Timeout) und meldet Fehler.

### User Story 5 – Prüfer erkennen indirekte Auswirkungen auf Eskalationsthemen (Priority: P1)

Befund 6 (mittel, fachlich wichtig): Die alte Pipeline eskalierte 084 („Score löst Auto-Versand aus“), der sak-Code-Prüfer genehmigte. Das Thema „echter Kontaktversand“ griff nur bei direkter Berührung von `messaging/`.

**Acceptance**: Die Anweisung des Code-Prüfers verlangt ausdrücklich, auch indirekte Auswirkungen auf `escalation.topics` zu prüfen (Datenfluss in Richtung der genannten Bereiche). Ein Regressionsfall nach dem Muster von 084 (Score-Änderung → Versandentscheidung) ist als Prüfer-Eval dokumentiert. Die projektspezifischen Pfade (Score, Ranking) sind Config-Sache von ImmoAgent und nicht Teil des Kits.

### User Story 6 – Ehrliche und vollständige Meldungen (Priority: P3)

- Befund 7: Der Init-Plan warnt, sobald `defaultMode: bypassPermissions` gesetzt ist. Im Trial fehlte die Warnung.
- Befund 8: `dashboard status` meldet `ok: false`, wenn `last_error` gesetzt ist. Ein 403 `project mismatch` nennt das erwartete Projekt (ohne Schlüssel).
- Befund 9: Der Plan führt die konkreten Allow- und Deny-Regeln auf und weist darauf hin, dass sie für das ganze Projekt gelten.
- Befund 10: Die Ausgabe erfolgt nicht doppelt (JSON oder Text, wählbar). `doctor` erklärt die Zahl der Lock-Einträge (config.yml und lock.json werden nicht verwaltet).

### User Story 7 – Vorbereitung frischer Checkouts (Priority: P3)

Befund 11: In frischen Worktrees fehlen gitignorierte, erzeugte Dateien (z. B. `web/src/api/schema.d.ts`, `node_modules`). Vorschlag: optionaler Config-Eintrag `commands.prepare`, den Builder und Prüfer vor dem Testen ausführen.

### Nachtrag 2026-10-21: Befunde aus dem Upgrade auf 0.1.1 (Trial Teil 2a)

- **B12 (mittel):** `sak doctor` über `sak.cmd` aus PowerShell oder cmd meldet `hook_probe` als nicht ok („keine POSIX-Shell (sh) gefunden“), obwohl Git-Bash installiert ist. Die Hooks selbst laufen in Claude Code über Git-Bash und funktionieren. Die Probe soll `sh` an bekannten Orten suchen (`%ProgramFiles%\Git\usr\bin\sh.exe`, `%ProgramFiles%\Git\bin\sh.exe`, `%LOCALAPPDATA%\Programs\Git\…`), analog zur uv-Suche.
- **B13 (niedrig):** Das Upgrade räumt überholte `permissions.allow`-Einträge des Kits nicht auf, zum Beispiel alte Testbefehle nach einer Config-Änderung. Kit-eigene allow-Einträge sollen sich wiedererkennen lassen (Herkunft im Lock vermerken) und beim Upgrade ersetzt werden. Fremde Einträge bleiben.
- **B14 (hoch, zu US2):** Der UI-Prüfer hat eine Junction `.spec-agent/state/runs/<id>/ui/node_modules` angelegt, die `git worktree remove` blockierte. Außerdem hat er durch einen Pfad mit Leerzeichen ohne Anführungszeichen die Ordner `Department/` und `Repos/` im Projekt erzeugt. Anforderung: Die Prüfer-Anweisung verbietet Links bzw. Junctions und verlangt quotierte Pfade. Ein Aufräumschritt am Lauf-Ende entfernt Links unter `runs/<id>/`. `reviewer-check` erkennt neue Top-Level-Ordner.
- **B15 (niedrig):** `doctor`/`dashboard` meldet ok, wenn das Dashboard erreichbar ist, auch ohne Schlüssel. Ok soll es erst sein, wenn ein Schlüssel vorhanden ist; optional folgt eine Auth-Probe ohne Datenänderung.
- **Zu US3 (Worktrees), Vorschlag des Planers:** Worktrees legt nur sak selbst an und räumt sie selbst wieder auf. Sie liegen an einem festen Ort (z. B. `<repo>.sak-runs/<lauf-id>`), erscheinen auf dem Board und werden mit `merged` bzw. `aborted` entfernt. `doctor` meldet übrig gebliebene Worktrees. Gemeinsame Dashboard-Einstellungen und der Schlüssel werden aus dem Haupt-Checkout geerbt.

### User Story 8 – Lauf-Kontext übersteht das Kompaktieren (Priority: P2)

Frage des Betreibers 2026-10-21: Kann das Framework `/compact` auslösen? Nein. Hooks und Skills können keine eingebauten Befehle ausführen. Das Kit sorgt aber dafür, dass der Orchestrator nach einer Kompaktierung (automatisch durch Claude Code oder manuell) den laufenden Lauf nicht verliert und ohne Rückfrage weiterarbeitet. Eine Empfehlung an den Betreiber, `/compact` auszuführen, gibt es ausdrücklich NICHT (Betreiber 2026-10-21: Agenten sollen autonom arbeiten). Ein programmatisches Auslösen (wie die Compact-API bei OpenCode) ist als Recherche-Punkt in `docs/follow-ups.md` vermerkt.

**Acceptance**:
1. **Given** ein aktiver Lauf, **When** die Sitzung kompaktiert wird, **Then** speist ein `SessionStart`-Hook (Matcher `compact`) eine Kurzfassung ein: Lauf-ID, Spec, Zustand, Runde, aktive Rollen, Muss-Befunde der letzten Runde, nächster Schritt laut Skill. Ohne aktiven Lauf: keine Ausgabe.

## Clarifications

### Session 2026-10-21 (Planer, Defaults nach Betreiber-Auftrag „alles Offene abarbeiten“)

- **US2/B14:**
  - Die UI-Prüfer-Anweisung lenkt Playwright-Ausgaben um (`--output` bzw. `PLAYWRIGHT_HTML_REPORT` nach `.spec-agent/state/runs/<id>/ui/`), verbietet Links und Junctions und verlangt quotierte Pfade.
  - `init` schlägt `clean_ignore` für `test-results/` und `playwright-report/` vor, wenn Playwright erkannt wird.
  - Neu ist `sak run cleanup <run>`: Es entfernt Links unter `runs/<id>/`, ohne ihnen zu folgen. Der Skill ruft es am Lauf-Ende auf; `abort` und `combine` rufen es selbst.
- **US3:** Kit-verwaltete Worktrees gehören zur späteren Spec „Parallelbetrieb“ (Regel siehe Nachtrag). In 011 gilt:
  - Erkennt die Engine einen Git-Worktree, erbt sie Dashboard-URL und Schlüssel aus dem Haupt-Checkout (git common dir).
  - `preflight` warnt, wenn das Sitzungsverzeichnis (`CLAUDE_PROJECT_DIR`) nicht der Checkout des Laufs ist.
- **US4:**
  - `init` liest `pyproject.toml`: pytest bzw. ruff in `optional-dependencies.<x>` ergibt `--extra <x>`, in `dependency-groups` ergibt nichts Zusätzliches.
  - `doctor --probe-commands` führt pytest-Befehle mit `--collect-only -q` aus (Timeout 60 s), andere Befehle nur mit `--version`, falls sinnvoll. Ohne Option wird nur geprüft, ob das Programm auffindbar ist.
- **US5:** Die Ergänzung im Code-Prüfer-Prompt prüft indirekte Auswirkungen auf `escalation.topics`. Das Eval steht als Dokument unter `docs/evals/indirect-escalation.md` und beschreibt Fall 084 anonymisiert.
- **US6:**
  - `--format json|text` für `init`, `upgrade` und `doctor` (Default `json` auf stdout, nichts doppelt).
  - Die bypass-Warnung erkennt `defaultMode` korrekt, auch im verschachtelten `permissions.defaultMode`.
  - `status`: `ok` ist false bei `last_error`. 403 nennt das Projekt.
  - Der Plan listet die allow- und deny-Regeln einzeln.
  - `doctor` erklärt die Lock-Zahl.
- **B12/B13/B15:** wie im Nachtrag beschrieben. Die vom Kit erzeugten allow-Einträge werden im Lock unter `settings_allow` vermerkt und beim Upgrade ersetzt.
- **US7:** `commands.prepare[]` (Contract aus 010 Strang 0) wird von Builder und Prüfern vor dem Testen ausgeführt (Prompt) und von `doctor --probe-commands` mitgeprüft.
- **US8:** `sak hook session-start` (stdin: Hook-Payload) gibt bei `source == "compact"` und aktivem Lauf JSON mit `hookSpecificOutput.additionalContext` aus, sonst nichts. Der Fragment-Eintrag `SessionStart` mit Matcher `compact` läuft über den Starter.

## Requirements *(mandatory)*

Die User Stories 1–8 und B12–B15 in Verbindung mit den Clarifications sind die Anforderungen. Jede wird mit einem Test abgesichert, oder es wird begründet, warum kein Test möglich ist (SC-002).

## Success Criteria *(mandatory)*

- **SC-001**: Ein Wiederholungslauf des Trials (Nur-Prüfung 084) in ImmoAgent erzeugt Stations-Events für beide Prüfer und erscheint auf specboard, ohne falsche `review_integrity`-Eskalation.
- **SC-002**: Für jeden Befund 1–4 und 6–11 gibt es einen automatisierten Test oder eine dokumentierte Begründung, warum nicht.
