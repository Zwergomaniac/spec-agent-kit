# Implementation Plan: Collector, lokales Board und Push

**Branch**: `006-collector-push` | **Date**: 2026-10-20 | **Spec**: [spec.md](spec.md)

## Technical Context

- **Sprache:** Python ≥ 3.11, nur Standardbibliothek (`urllib.request`, `http.server`, `subprocess`) plus `jsonschema` und `pyyaml`.
- **Abhängigkeiten:** Spec 002 (`contracts.py`), 003 (`pipeline.runs`, `pipeline.events`, Hooks), 004 (`config`).
- **Tests:** pytest, Fixture-Repo, ein lokaler Test-HTTP-Server in einem Thread.

## Constitution Check

| Prinzip | Erfüllt durch |
|---|---|
| I | Validierung des Boards vor jeder Ausgabe; Ingest nach Contract |
| II | Ticker-Text ist opt-in; es wird nur Validiertes gesendet |
| IV | Loopback-Server, Host-Prüfung; Schlüssel nur aus Env oder gitignorierter Datei; HTTPS-Pflicht |
| VI | Ableitung aus `dev_board.py` portiert (GitHistory, `_station`, Marker-Regex, `render_text`, `make_server`); `index.html` portiert |
| VIII | keine Projektpfade; feature_status- und Queue-Logik entfällt (Plugin) |

## Project Structure

```text
packages/engine/src/spec_agent_kit/board/
  __init__.py
  git_history.py   # Port von GitHistory: ein git log --reverse --name-only mit RS/US-Trennern
  specs.py         # Spec-Scan: Titel, Station, Tasks, descoped, Klärung, Betreiber-Tasks
  runs_view.py     # Läufe + Events → runs[] (Stationen, Urteile, Eskalationen, idle/stale)
  build.py         # build_board(root, cfg, source="live") -> dict ; validiert
  text.py          # render_text (≤ 40 Zeilen)
  serve.py         # Loopback-Server
  static/board.html
packages/engine/src/spec_agent_kit/push/
  __init__.py
  outbox.py        # Cursor, Lesen ab Offset, kaputte Zeilen
  client.py        # HTTP-Ingest, Fehlerklassen
  run.py           # push(root, quiet) ; spawn_background(root)
packages/engine/src/spec_agent_kit/cli.py   # board [--text|--json] | board serve ; push [--background] [--quiet]
packages/engine/src/spec_agent_kit/pipeline/{hooks.py,commands.py}  # FR-011 Auslöser
packages/engine/tests/board/  tests/push/
packages/engine/tests/fixtures/board_repo/   # Skript, das das Fixture-Repo deterministisch erzeugt (feste Commit-Daten über GIT_AUTHOR_DATE/GIT_COMMITTER_DATE)
```

## Abweichungen von der Referenz

| `dev_board.py` | Neu | Grund |
|---|---|---|
| deutsche Schlüssel (`kennzahlen`, `mensch_prueft`) | `sak.board/1` (englisch) | Spec 002 |
| `feature_status.py`-Import, blockers.yml, deferred-decisions | eigener schlanker Spec-Scan; Blocker/Entscheidungen über Plugin | ADR E6 |
| Snapshot beim Deploy (`reduce_for_snapshot`) | Push an das Dashboard; `source: snapshot` nur, wenn ohne Läufe exportiert wird | ADR E2 |
| ein Lauf (`agenten.run`) | `runs[]` | Spec 001 |
| LAN-Modus (geplant) | entfällt | Push ersetzt ihn (092 stage2-draft) |

## Complexity Tracking

Keine Verstöße.
