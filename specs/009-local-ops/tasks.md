# Tasks: Lokale Bedienung und Betrieb

**Input**: [spec.md](spec.md), [plan.md](plan.md). Die Stränge A und B laufen parallel. Die Agents haken hier NICHT ab, das macht der Planer nach dem Merge.

## Strang A – Engine (Python)

- [ ] A01 [US1] Vorlagen `packages/agent-blueprint/templates/spec-agent/sak.cmd` und `sak` (FR-002).
- [ ] A02 [US1] Init und Upgrade verwalten beide Starter (Lock), setzen das Ausführbar-Bit; Tests in `tests/install`.
- [ ] A03 [US1] Tests für die Starter: Windows-Test führt `sak.cmd version` mit `SAK_UV` und mit leerem PATH aus (skip auf Nicht-Windows); POSIX-Test analog mit `sh` (skip auf Windows ohne sh); Fehlerfall Exit 127.
- [ ] A04 [US2] `sak board serve`: Port-Ausweichen, `--open`; Tests.
- [ ] A05 [US4] `sak dashboard connect` und `sak dashboard status`; Tests: Plan ohne `--yes`, Kommentare bleiben, ungültige Config → Rollback, Schlüsselformat, `--force`, nie Schlüssel in der Ausgabe, Test-Push gegen lokalen Test-Server.
- [ ] A06 Alles grün: `pytest -q`, `ruff check`.

## Strang B – Dashboard und Deploy (TS/Bash)

- [ ] B01 [US7] `.dockerignore`; Runtime-Stage mit `"type": "module"`.
- [ ] B02 [US3] `HOST` in `env.ts` (Default `0.0.0.0`); `scripts/local.mjs`; Root-Skripte `dashboard:local` und `dashboard:project`; `.local/` in `.gitignore`. Tests für Env-Parser und erstes Anlegen.
- [ ] B03 [US5] `GET /api/portfolio` erweitert (FR-007), Vertragstests.
- [ ] B04 [US5] `ProjectCard.tsx`: Stretched Link, Hover, Fokus, „Board öffnen →“, Stationsbalken mit Tooltip, fertige Specs, Vorschau der Aufmerksamkeitseinträge, letzter Marker; Unit-Tests.
- [ ] B04b [US5] Layout volle Breite (US5 Szenario 5): Seiten-Container in Portfolio, Projekt, Lauf und Admin; Portfolio-Grid `auto-fill` und `minmax`. Prüfen bei 1440, 1920 und 2560 px Breite.
- [ ] B05 [US5] Playwright (inkl. Screenshots Portfolio bei 1920 px): Klick auf die Kartenfläche, Strg+Klick, innere Links, Tastatur (Tab und Enter), Hover-Screenshot.
- [ ] B06 [US6] `deploy/dashboard/deploy-vps.sh`, `vps.env.example`, `vps.env` in `.gitignore`; `bash -n`; Trockenlauf mit `--dry-run` und einer Beispiel-`vps.env` im Scratchpad.
- [ ] B07 Alles grün: `pnpm -r test`, `pnpm -r lint`, `pnpm -r build`, E2E.

## Abschluss (Planer)

- [ ] C01 Merge beider Stränge, Gesamttest.
- [ ] C02 Doku (FR-010).
- [ ] C03 Deploy auf specboard mit dem neuen Skript; Upgrade des AI-Forge-Pilot-Inits mit den Startern (uncommittet).
