# Implementation Plan: Lokale Bedienung und Betrieb

**Branch**: `009-local-ops` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

## Aufteilung

Die Umsetzung läuft auf zwei parallelen Strängen mit getrennten Dateien.

| Strang | Branch | Inhalt | Dateien |
|---|---|---|---|
| A (Python) | `009-local-ops-engine` | US1, US2, US4 | `packages/engine/**`, `packages/agent-blueprint/templates/spec-agent/**` |
| B (TS/Deploy) | `009-local-ops-dashboard` | US3, US5, US6, US7 | `apps/**`, `deploy/dashboard/**`, `package.json`, `.dockerignore`, `.gitignore` |

Doku (FR-010) und das Abhaken in `tasks.md` erledigt der Planer nach dem Merge.

## Constitution Check

| Prinzip | Erfüllt durch |
|---|---|
| III | `connect` schreibt nur mit `--yes`, erhält Kommentare und rollt bei ungültiger Config zurück. Die Starter werden verwaltet (Lock). |
| IV | Der Schlüssel erscheint nie in Ausgaben. Rechte 600. Der Deploy fasst `.env` und Caddy nicht an. Der lokale Server bindet nur an Loopback. |
| VII | Tests je Story, Playwright für die Karte |
| VIII | Die Starter sind plattformneutral. Keine Projektwerte im Deploy-Skript (alles aus `vps.env`). |

## Technische Details

- **Starter Windows (`sak.cmd`):** Batch mit `setlocal`. Für den WinGet-Packages-Glob wird `for /d` genutzt. Ohne Fund: Meldung `winget install --id astral-sh.uv -e` und `exit /b 127`.
- **Starter POSIX (`sak`):** `#!/bin/sh`, `command -v`, Liste fester Orte. Ohne Fund: Meldung `curl -LsSf https://astral.sh/uv/install.sh | sh` und `exit 127`.
- **Ausführbar-Bit:** Init und Upgrade setzen es über `os.chmod` (POSIX). Im Lock wird es nicht abgebildet.
- **Port-Ausweichen:** Port-Suche über bind-Versuche ohne `SO_REUSEADDR`, wie bisher.
- **`connect`:**
  - Schlüssel über `getpass.getpass` oder stdin (`--key-stdin`), Regex `^sak_[A-Za-z0-9_-]{43}$`.
  - Config-Änderung über eine Regex auf den Block `dashboard:`, nur die erste Zeile `^\s+url:`. Fehlt sie, wird sie eingefügt.
  - Danach `config.load` und Prüfung. Bei Fehler wird zurückgeschrieben.
- **`dashboard:local`:** `apps/dashboard-api/scripts/local.mjs`
  - prüft `dist` und baut über `pnpm -r build`, wenn etwas fehlt
  - liest und schreibt `.local/dashboard.env` (dotenv-Format, eigener kleiner Parser)
  - Passwort über einen versteckten TTY-Prompt (Logik wie `cli/hash-password`, wiederverwendet)
  - startet `dist/server.js` mit Env `HOST=127.0.0.1`. Fehlt `HOST` in `env.ts`, wird es ergänzt, Default `0.0.0.0` für den Container.
- **`dashboard:project`:** reicht an `dist/cli/project.js` durch, mit derselben Env.
- **Portfolio-API:** `services/portfolio.ts` wird erweitert, `ProjectCard.tsx` neu gestaltet (Stretched Link: `<a className="after:absolute after:inset-0">` auf dem Titel; innere Links `relative z-10`).
- **`deploy-vps.sh`:**
  - `set -euo pipefail`
  - lädt `vps.env` (`VPS_HOST`, `VPS_USER`, `VPS_PORT`, `VPS_SSH_KEY`, `REMOTE_DIR`, `COMPOSE_PROJECT`)
  - Prüfung `git diff --quiet && git diff --cached --quiet`
  - `git archive HEAD | ssh … "rm -rf $REMOTE_DIR/src.new && mkdir … && tar -x -C $REMOTE_DIR/src.new"`
  - Build aus `src.new`. Bei Erfolg wird `src` → `src.prev` und `src.new` → `src`, dann `docker compose up -d`.
  - Danach max. 60 s auf `healthy` warten und `/healthz` im Container prüfen.
  - Optionen `--dry-run` und `--prune`.

## Complexity Tracking

Keine Verstöße.
