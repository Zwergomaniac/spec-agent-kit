# Architektur v1

Stand 2026-10-20. Verbindlich für die Specs 002 bis 007. Die Grundlage sind ADR 0001 und die Constitution.

## Bausteine

```text
┌──────────────── Zielprojekt (z. B. AI-Forge) ────────────────┐
│ .claude/agents/sak-*.md      Rollen (builder, code_review…)   │
│ .claude/skills/sak-*/        Orchestrator-Skill, Init-Skill   │
│ .claude/settings.json        Hooks (gemergt, nicht ersetzt)   │
│ .spec-agent/config.yml       Projektkonfiguration (Spec 004)  │
│ .spec-agent/lock.json        Kit-Version + Datei-Hashes (005) │
│ .spec-agent/engine/          vendorte Engine (uv-Projekt)     │
│ .spec-agent/state/  (ignored) runs/, events.jsonl, outbox/    │
│ specs/NNN-*/                 spec-kit-Artefakte (Upstream)    │
└──────────────┬───────────────────────────────────────────────┘
               │ sak push (HTTPS, Projekt-Schlüssel, Spec 006)
               ▼
┌──────────── VPS: Container spec-agent-dashboard ─────────────┐
│ Hono-API (/api/ingest, /api/read, /auth) + gebaute React-UI   │
│ SQLite (WAL) unter /data, nur Metadaten (Spec 007)            │
└──────────────── hinter externem edge-caddy ──────────────────┘
```

## Repo-Layout (dieses Repo)

```text
packages/
  contracts/            Quelle der Wahrheit (Spec 001/002)
    schema/             *.schema.json (JSON Schema 2020-12), vocabulary.json, labels/de.json
    src/                TS-Paket @sak/contracts: Zod-Schemas (generiert) + Typen + Deep Links
    scripts/            Generator schema → Zod, Sync → Python
  engine/               Python-Paket spec_agent_kit (uv-Projekt), CLI `sak`
    src/spec_agent_kit/
      schemas/          Kopie von contracts/schema (per Sync, Test prüft Gleichheit)
      pipeline/         Zustandsmaschine, guard, snapshot, verdict, combine, hooks (Spec 003)
      config/           Laden und Validieren von .spec-agent/config.yml (Spec 004)
      board/            Collector: Board-Dokument aus Dateien und Git (Spec 006)
      push/             Outbox und Push ans Dashboard (Spec 006)
      install/          init, upgrade, Lockfile, Settings-Merge (Spec 005)
    tests/
  agent-blueprint/
    templates/          Dateien für Zielprojekte (Agents, Skills, config.yml, settings-Fragment)
apps/
  dashboard-api/        Hono + SQLite + Auth, liefert apps/dashboard-web/dist aus (Spec 007)
  dashboard-web/        React + Vite + Tailwind/shadcn (Spec 007)
deploy/dashboard/       Dockerfile, compose.snippet.yml (edge-caddy-Netz extern)
```

## Laufzeit-Regeln

- **CLI `sak`** (Python ≥ 3.11), immer über uv:
  - im Kit-Repo: `uv run --project packages/engine sak …`
  - im Zielprojekt: `uv run --project .spec-agent/engine sak …`
- **Die Engine wird ins Zielprojekt vendort** (`.spec-agent/engine/`, inklusive `uv.lock`). Das hält das Zielprojekt selbständig: kein Netz nötig, prüfbar, ein geschützter Pfad. `sak upgrade` ersetzt sie anhand des Lockfiles.
- **Ausgabe:** JSON auf stdout. Exit-Codes: 0 bei Erfolg, 1 bei fachlicher Ablehnung, 2 bei Bedienfehler. Hook-Befehle enden immer mit 0.
- **Plattform:** Die Engine stellt stdout und stderr selbst auf UTF-8 um (`reconfigure`). Pfade laufen nur über `pathlib`. Es gibt keine Interpreter-Pfade, keine Shell-Annahmen und kein `PYTHONIOENCODING`.
- **Pflicht-Abhängigkeiten der Engine:** `pyyaml`, `jsonschema`. HTTP nur über die Standardbibliothek (`urllib`).
- **Dashboard:** Node 22+, pnpm 10.
  - Pakete: `hono`, `@hono/node-server`, `better-sqlite3`, `zod`, `react`, `vite`, `tailwindcss`, shadcn/ui, `lucide-react`, `recharts`.
  - Ein Container, Port 3000, Volume `/data`.

## Datenfluss

1. Hooks (`SubagentStart`/`SubagentStop`) und Pipeline-Befehle schreiben Events nach `.spec-agent/state/events.jsonl`. Jedes Event steckt bereits in der v1-Hülle (Spec 002).
2. `sak board` erzeugt das Board-Dokument aus `specs/`, Git, Runs und Events. Es nutzt keine zweite Status-Quelle.
3. `sak push` sendet neue Events und den aktuellen Board-Snapshot an das Dashboard.
   - Der Push ist ausfallsicher: Timeout 3 s, eine Outbox, und er blockiert nie die Pipeline.
   - Auslöser: am Ende der Hooks, im Hintergrund, oder manuell.
4. Das Dashboard speichert pro Projekt den letzten Snapshot und alle Events (Retention 30 Tage). Daraus entstehen Portfolio, Projekt- und Lauf-Ansichten.

## Bewusste Abweichungen von ImmoAgent (Constitution VI)

| ImmoAgent | v1 | Grund |
|---|---|---|
| `.specify/pipeline.yml` + `.specify/scripts/python/pipeline.py` | `.spec-agent/config.yml` + vendorte Engine | Kit-Dateien sind sauber von spec-kit-Upstream getrennt |
| `runs/<spec>/run.json` | `runs/<run_id>/run.json` | Historie bleibt erhalten (Spec 001 FR-009) |
| flaches `events.jsonl` | Event-Hülle v1 | Push und Idempotenz (Spec 002) |
| deutsche Urteilszeile `Urteil: …` | Zeile `Verdict: approve\|changes_requested\|needs_human`; Locale `de` akzeptiert zusätzlich `Urteil: OK\|Änderung\|Mensch prüft` | englische Maschinenwerte (ADR E4) |
| feste Stationen `code`/`ui` | Rollenliste aus der Config | ADR E8 |
| Board eingebettet in die App, Snapshot beim Deploy | eigener Dashboard-Container, Push | ADR E10 |
| `bypassPermissions` | restriktiver Default | Constitution IV |
