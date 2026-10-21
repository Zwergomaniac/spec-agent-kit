# Tasks: Ein Board, zwei Orte

**Input**: [spec.md](spec.md) (Clarifications und FR-001 bis FR-007), [../../docs/architecture.md](../../docs/architecture.md), Contracts-Workflow aus [../../packages/contracts/AGENTS.md](../../packages/contracts/AGENTS.md).

**Plan in Kürze:** Die Umsetzung läuft in drei Strängen.

| Strang | Zeitpunkt | Branch | Inhalt | Dateien |
|---|---|---|---|---|
| 0 Contracts | zuerst | `010-contracts` | alle Schema-Änderungen, auch die von Spec 011 | `packages/contracts/**` und die Schema-Kopie in der Engine |
| A Engine | danach parallel zu B | `010-engine` | Python-Teil | `packages/engine/src/spec_agent_kit/{board,migrate,plugins,config}/**`, `cli.py`, Tests, `templates/config/examples/*` |
| B Web | danach parallel zu A, im Worktree | `010-web` | lokaler Modus der UI, Tooltips, Ticker, Build ins Engine-Verzeichnis | `apps/dashboard-web/**`, Root-`package.json`; `packages/engine/src/spec_agent_kit/board/web/**` (nur generiert) |

Am Ende merged der Planer. Die Agents haken hier nicht ab, das macht der Planer.

## Strang 0 – Contracts

- [ ] T001 `board.schema.json`: optionales `ticker[].commit` (Pattern 7–40 hex), optionales `specs[].tasks.partial` (≥ 0).
- [ ] T002 `config.schema.json`:
  - `plugins` als Liste von `{name: enum ["legacy-status"], options?: object}` mit `maxItems` 10
  - optionales `commands.prepare[]` (für Spec 011 US7)

  Defaults in der Engine anpassen.
- [ ] T003 Beispiele (gültig und ungültig), `pnpm contracts:gen`, Tests in TS und Python grün.

## Strang A – Engine

- [ ] A01 [US6] Parser-Regeln (FR-007) in `board/specs.py`, mit je einem Regressionstest pro Punkt 1–7 aus US6 (minimale Fixtures).
- [ ] A02 [US6] Kennzahl „fertig“ nach Clarification (Station ≥ implemented UND 0 offen bzw. teilweise); `tasks.partial` befüllen; `--text` mit lokaler Zeit und Zone.
- [ ] A03 [US2] `ticker[].commit` befüllen (kurzer Hash). Beispiel-Configs ImmoAgent und AI-Forge: `share_commit_subjects: true`.
- [ ] A04 [US5] Plugin-Mechanismus (Laden nach Config, Fehler isoliert, Hinweis statt Absturz) und Plugin `legacy-status` (FR-006). Tests mit Fixtures im ImmoAgent-Format (Formate aus `ImmoAgent/.specify/scripts/python/feature_status.py`, nur lesen).
- [ ] A05 [US4] `sak migrate legacy-pipeline` (FR-005): Plan ohne `--apply`, deterministische IDs, Idempotenz-Test, Mapping-Tests für alle alten Event-Arten. Optionaler Test gegen eine Kopie von `ImmoAgent/.specify/pipeline` hinter `SAK_IMMOAGENT_PIPELINE` (nur lesen, arbeitet auf einer tmp-Kopie).
- [ ] A06 [US1] `board/serve.py`: Lese-API nach FR-001 (gleiche Formen wie `apps/dashboard-api`; dort nur lesen), statische Auslieferung von `board/web/` mit SPA-Fallback. `static/board.html` entfernen. Solange `board/web/` fehlt, kommt eine klare Meldung. Tests der API-Formen gegen die Zod-Schemas bzw. die Python-Validierung.
- [ ] A07 Alles grün (`pytest -q`, `ruff`). Optionaler ImmoAgent-Vergleich hinter `SAK_IMMOAGENT_SPECS`: Zahlen im Bericht.

## Strang B – Web

- [ ] B01 [US1] Lokaler Modus: `/api/meta` mit `mode: "local"` → kein Login, Portfolio und Admin ausgeblendet, Start `#/project/<key>`. Der Header zeigt „Lokal“ und den Projektnamen.
- [ ] B02 [US1] Build-Ziel `build:local` mit Ausgabe nach `packages/engine/src/spec_agent_kit/board/web/` (relative Pfade, keine externen Ressourcen). Root-Skripte `board:build` und `board:check` (bauen und `git diff --exit-code`).
- [ ] B03 [US2] Ticker: Hover- bzw. Fokus-Details (Hash, lokale Zeit mit Zone, Spec, Betreff), tastaturbedienbar.
- [ ] B04 [US3] Tooltips für alle Kennzahlen und Spaltenköpfe (Definitionen zentral in einer Datei).
- [ ] B05 [US6] Anzeige von `tasks.partial`, falls vorhanden.
- [ ] B06 E2E: lokaler Modus gegen einen Mock-Server mit denselben Endpunkten. Screenshot-Vergleich lokal ↔ online für dieselben Daten (SC-001), Ticker-Hover, Tooltips. Alles grün.

## Abschluss (Planer)

- [ ] C01 Merge der Stränge 0, A und B; `board:build` auf main; Gesamttest; Doku (README, architecture: Board-Ableitungsregeln, lokaler Modus); Deploy auf specboard.
