# Feature Specification: Robustheit aus dem ImmoAgent-Trial

**Feature Branch**: `011-trial-hardening`

**Created**: 2026-10-21

**Status**: Draft (nicht geplant; Befund 1 vorab als Hotfix umgesetzt)

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

## Requirements *(mandatory)*

Noch nicht ausgearbeitet. Folgt bei `/speckit-clarify` und `/speckit-plan`.

## Success Criteria *(mandatory)*

- **SC-001**: Ein Wiederholungslauf des Trials (Nur-Prüfung 084) in ImmoAgent erzeugt Stations-Events für beide Prüfer und erscheint auf specboard, ohne falsche `review_integrity`-Eskalation.
- **SC-002**: Für jeden Befund 1–4 und 6–11 gibt es einen automatisierten Test oder eine dokumentierte Begründung, warum nicht.
