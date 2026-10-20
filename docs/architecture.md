# Architektur v1

Stand 2026-10-20, Umsetzungsstand der Specs 001 bis 007 ergänzt. Verbindlich für die Specs 002 bis 007. Die Grundlage sind ADR 0001 und die Constitution.

## Bausteine

```text
┌──────────────── Zielprojekt (z. B. AI-Forge) ────────────────┐
│ .claude/agents/sak-*.md      Rollen (builder, code_review…)   │
│ .claude/skills/sak-*/        Orchestrator-Skill, Init-Skill   │
│ .claude/settings.json        Hooks (gemergt, nicht ersetzt)   │
│ .spec-agent/config.yml       Projektkonfiguration (Spec 004)  │
│ .spec-agent/lock.json        Kit-Version + Datei-Hashes (005) │
│ .spec-agent/engine/          vendorte Engine (uv-Projekt)     │
│ .spec-agent/state/  (ignored) runs/, events.jsonl, push-*     │
│ specs/NNN-*/                 spec-kit-Artefakte (Upstream)    │
└──────────────┬───────────────────────────────────────────────┘
               │ sak push (HTTPS, Projekt-Schlüssel, Spec 006)
               ▼
┌──────────── VPS: Container spec-agent-dashboard ─────────────┐
│ Hono-API (/api/ingest, /api/auth, /api/admin, Lese-API) + UI  │
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
- **CLI-Befehle** (Stand `sak --help`): `version`, `config check|show`, `board [--json|--text]`, `board serve`, `push`, `init`, `upgrade`, `doctor`, `run <preflight|state|pause|release|abort|return|resume|guard|combine|merge|show|snapshot|reviewer-check|verdict|list>`, `hook subagent-start|subagent-stop`, `event emit`.
- **Ausgabe:** JSON auf stdout. Exit-Codes: 0 bei Erfolg, 1 bei fachlicher Ablehnung, 2 bei Bedienfehler. Hook-Befehle enden immer mit 0.
- **Plattform:** Die Engine stellt stdout und stderr selbst auf UTF-8 um (`reconfigure`). Pfade laufen nur über `pathlib`. Es gibt keine Interpreter-Pfade, keine Shell-Annahmen und kein `PYTHONIOENCODING`.
- **Pflicht-Abhängigkeiten der Engine:** `pyyaml`, `jsonschema`. HTTP nur über die Standardbibliothek (`urllib`).
- **Dashboard:** Node 22+, pnpm 10.
  - Pakete: `hono`, `@hono/node-server`, `better-sqlite3`, `zod`, `react`, `vite`, `tailwindcss`, shadcn/ui, `lucide-react`, `recharts`.
  - Ein Container, Port 3000, Volume `/data`.

## Datenfluss

1. Hooks (`SubagentStart`/`SubagentStop`) und Pipeline-Befehle schreiben Events nach `.spec-agent/state/events.jsonl`. Jedes Event steckt bereits in der v1-Hülle (Spec 002).
2. `sak board` erzeugt das Board-Dokument aus `specs/`, Git, Runs und Events. Es nutzt keine zweite Status-Quelle.
3. `sak push` sendet neue Events und den aktuellen Board-Snapshot an das Dashboard. Die Outbox ist `events.jsonl` selbst; ein Cursor (`push-cursor.json`) merkt den Stand, `push.lock` verhindert doppelte Läufe, `push-rejected.jsonl` führt abgelehnte Events (nur ID und Grund).
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

## Umsetzungsstand und Abweichungen vom Plan

Alle Specs 001 bis 007 sind umgesetzt (Spec 008, der Pilot, steht aus). Die Details stehen in den Anmerkungen der jeweiligen `tasks.md`. Hier die wesentlichen Lesarten und Abweichungen.

**Contracts (001, 002)**

- Zusätzliche Vokabular-Ebenen, damit jedes Enum im Vokabular steht: `diag_event_type`, `board_source`, `hook_phase`. `run_kind` enthält auch `manual` (reserviert).
- `marker_kind` und `ticker_kind` teilen Werte mit anderen Ebenen (`deploy`, `verified`). Sie sind von der Eindeutigkeitsprüfung (Spec 001 SC-002) ausgenommen; der Test dokumentiert das.
- In Schema-Mustern keine Backslashes (`[0-9]` statt `\d`): der Zod-Generator verdoppelt sie nicht. Der generierte Zod-Code ist unformatiert.
- Top-Level `anyOf` statt `oneOf`, damit `json-schema-to-zod` typisierte Unions erzeugt. Größenlimits stehen in `schema/limits.json` für TS und Python.
- `propertyNames` und `allOf` bildet der Generator nicht ab. In `config.schema.json` sind deshalb die sechs Rollen ausgeschrieben (Integrator mit `enabled: const false`); ein Test gleicht sie mit dem Vokabular ab.

**Pipeline-Engine (003)**

- Zusätzlich erlaubter Übergang `paused → escalated`: ein aus `escalated` pausierter Lauf kehrt bei `resume` in den Zustand vor der Pause zurück (Spec 001 FR-011 ist nachgetragen).
- `building → reviewing` schreibt kein Event, weil das Vokabular dafür keinen Ereignistyp hat (wie in der Referenz). Ein optionales Event steht in den [Follow-ups](follow-ups.md).
- Bei der Übernahme eines verwaisten Laufs entsteht nur `run.taken_over`, kein zusätzliches `run.aborted`.
- `combine` lehnt bei fehlendem Urteil ab (statt `complete: false`) und führt den Zustandswechsel selbst aus. `merge` pusht nie und bricht bei Konflikt ab (`git merge --abort`, Lauf `escalated`).
- Der Basis-Branch kommt aus der Config; `--base` ist auf dem Spec-Branch nicht mehr Pflicht. `--review-only` nimmt `--base-commit`. Lauf-IDs bekommen bei gleicher Sekunde einen Suffix (`-b`, `-c`).
- Hooks schreiben nichts auf stdout und enden immer mit Exit 0. `diag.hook` entsteht je Phase einmal, nur bei fehlendem Agent-Typ und aktivem Lauf.

**Konfiguration, Init, Upgrade (004, 005)**

- Die Config-Locale ist in v1 immer `de`. `config check` meldet fehlende `model`/`effort` im Agent-Frontmatter als Warnung, echte Abweichungen als Fehler.
- Ein zweites `sak init` wird abgelehnt (Verweis auf `upgrade`). Als initialisiert gilt, wenn `.spec-agent/lock.json` existiert.
- Lock-Hash: SHA-256 über den Inhalt, Zeilenenden bei Textdateien auf LF normalisiert (autocrlf-fest).
- Kit-Wurzel: `kit_root()` leitet sie fünf Ebenen über `install/kit.py` ab (`packages/engine/src/spec_agent_kit/install/kit.py`). In der vendorten Kopie im Zielprojekt fehlen die Vorlagen, dann gibt es keine Kit-Wurzel; Init und Upgrade laufen nur aus dem Kit-Repo.
- `.spec-agent/.gitignore` enthält `state/`, `dashboard.key`, `engine/.venv/` und `__pycache__/`, damit die vendorte Engine keinen unsauberen Arbeitsstand erzeugt.
- `uv sync` läuft als `uv sync --project .spec-agent/engine --locked`. Exit 1 nach `--apply` heißt: geschrieben ist alles, aber `uv sync` oder `config check` ist fehlgeschlagen.
- Der Skill `sak-init` liegt im Kit-Repo (`.claude/skills/sak-init`) und ist keine Vorlage für Zielprojekte.

**Collector und Push (006)**

- Das Dashboard antwortet auf Einzelfehler mit 200 und `rejected[]`. Diese Events gehen ins Abgelehnt-Protokoll, der Cursor rückt vor.
- Ein 400 auf die ganze Anfrage ist systemisch: der Cursor bleibt, die Ursache wird gemeldet. „unsupported schema version“ und „unknown event type“ gelten als Versionsfehler, der Cursor bleibt ebenfalls. Ablehnungen des Boards (`board: …`) blockieren die Events nicht.
- Das Board geht nur mit der Anfrage, die den Rückstand leert, und nur bei geändertem Inhalt (Hash ohne `generated_at`). Batches sind auf 1,2 MB begrenzt.
- Der Client folgt keinen Weiterleitungen, nutzt für Loopback keinen Proxy und erlaubt `http://` nur für `localhost` und `127.0.0.1`.
- `sak board serve` bindet nur 127.0.0.1, ohne `SO_REUSEADDR` (Windows), Default-Port 5192; belegte Ports ergeben Exit 2. `metrics.blocked` ist in v1 immer 0.

**Dashboard (007)**

- Die API wird mit esbuild gebündelt (`apps/dashboard-api/scripts/build.mjs`), weil `@sak/contracts` TypeScript-Quellen exportiert; `tsc` läuft nur als `lint`. Nur `better-sqlite3` bleibt extern.
- Tailwind v4 (`@tailwindcss/vite`): kein `tailwind.config.ts`, die Tokens stehen in `src/index.css`. Die shadcn-Bausteine sind von Hand eingecheckt.
- Passwort-Hash im Format `scrypt:N:r:p:salt:hash` (ohne `$`); Projekt-Schlüssel `sak_<43 Zeichen base64url>`.
- Das Projekt ergibt sich aus dem Bearer-Schlüssel; abweichendes `project` in der Hülle ergibt 403. Retention gilt für den Event-Zeitstempel `ts`.
- Warnungen `idle` und `no_push_24h` des Portfolios sind kein Vokabular; die Texte stehen in der UI (`ProjectCard.tsx`).
- Tab `operator` aus dem frühen Konzept entfällt, es gelten `board|runs|attention|conflicts`. `conflicts` ist in v1 ein Hinweis (siehe [dashboard-concept](ui/dashboard-concept.md)).
- Playwright-E2E (Port 3100, frische DB) läuft nur lokal. Das Dockerfile wurde noch nie gebaut.
