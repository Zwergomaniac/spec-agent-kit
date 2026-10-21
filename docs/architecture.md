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
- **CLI-Befehle** (Stand `sak --help`): `version`, `config check|show`, `board [--json|--text]`, `board serve`, `push`, `init`, `upgrade`, `doctor`, `run <preflight|state|pause|release|abort|return|resume|guard|combine|merge|show|snapshot|reviewer-check|verdict|list|cleanup>`, `hook subagent-start|subagent-stop|session-start`, `event emit`. `init`, `upgrade` und `doctor` nehmen `--format json|text`; `doctor` zusätzlich `--probe-commands`.
- **Ausgabe:** JSON auf stdout (bei `init`, `upgrade`, `doctor` wählbar: `--format text` ergibt Text statt JSON, nie beides). Exit-Codes: 0 bei Erfolg, 1 bei fachlicher Ablehnung, 2 bei Bedienfehler. Hook-Befehle enden immer mit 0.
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

## Board-Ableitungsregeln

Das Board entsteht bei jedem Aufruf neu aus `specs/`, Git, Läufen und Events (Spec 006, Spec 010). Diese Regeln gelten lokal (`sak board`, `sak board serve`) und im Push gleich. Sie sind absichtlich eigenständig und weichen an einigen Stellen vom alten ImmoAgent-Board ab (siehe unten).

**Task-Zeilen (`tasks.md`)**

- Eine Task-Zeile ist jede Markdown-Aufzählung mit Checkbox: Aufzählungszeichen `-`, `*`, `+` oder eine Nummer mit `.` oder `)`, auch eingerückt (Unteraufgaben zählen mit). Die Checkbox ist `[ ]` (offen), `[x]` oder `[X]` (erledigt) oder `[~]` (teilweise).
- Eine Task-ID (`T001`) ist nicht nötig. Zeilen ohne Aufzählungszeichen, mit `[]` oder mit `-[ ]` (ohne Leerzeichen) zählen nicht.
- `[~]` ist weder erledigt noch offen. Es erscheint als eigenes Feld `tasks.partial` (nur wenn größer 0). Eine Spec mit teilweisen Tasks hat die Umsetzung nicht abgeschlossen.
- Ein Codeblock beginnt nur mit einem Fence (mindestens drei Backticks oder Tilden) am Zeilenanfang, höchstens 3 Leerzeichen eingerückt, und nur wenn er nicht zu einer Aufzählung gehört. Ein eingerückter Fence in der Folgezeile einer Aufzählung (ab 4 Leerzeichen immer, bei 1 bis 3 Leerzeichen innerhalb einer Aufzählung) ist Text, kein Codeblock. Der Block endet mit einem Fence derselben Art und mindestens derselben Länge. Zeilen darin zählen nicht.
- Code-Spans (`` `…` ``) werden für die Marker-Erkennung ignoriert: `` `**[Betreiber]**` `` im Text macht aus einer Task keine Betreiber-Aufgabe. Im angezeigten Grund bleiben Code-Spans erhalten. Nur der Marker außerhalb von Code-Spans wird entfernt.
- Betreiber-Aufgaben: je offene Task mit `[operator]` oder `**[Betreiber]**` außerhalb von Code-Spans ein Eintrag `operator_task`. Teilweise und erledigte Tasks erzeugen keinen.

**Station, „fertig“ und „in Arbeit“**

- Die Station folgt Spec 001 FR-006 (höchste zutreffende Bedingung). `implemented` setzt voraus: mindestens eine erledigte Task, keine offene, keine teilweise. Mit offenen oder teilweisen Tasks (und mindestens einer erledigten oder teilweisen) ist die Station `implementing`.
- Marker (`deploy(…)`, `verified(…)`) sind Fakten und bleiben erhalten: Eine Spec mit Marker bleibt `deployed` bzw. `verified`, auch wenn später Tasks offen sind.
- **Fertig** (Kennzahl `done`) ist eine Spec, wenn ihre Station `implemented`, `deployed` oder `verified` ist **und** sie 0 offene und 0 teilweise Tasks hat. Durchlaufzeit und `finished_at` gibt es nur für fertige Specs.
- **In Arbeit** (`in_progress`) ist eine Spec in Station `implementing` oder mit fertiger Station, aber offenen bzw. teilweisen Tasks. Beides schließt sich aus: Jede Spec zählt höchstens einmal.
- **Blockiert** (`blocked`) zählt Specs mit `blocked: true`. Diese Markierung setzt nur ein Plugin (`legacy-status`); ohne Plugin ist der Wert 0.
- **Wartet** (`waiting`) zählt alle Aufmerksamkeitseinträge: `escalation`, `stale_run`, `approval`, `clarification`, `operator_task` und, durch Plugins, `blocker` und `decision`.

**Zurückgestellt (`descoped`)**

- Quelle 1: `**Status**: Descoped` im Kopf der `spec.md` (vor der ersten `## `-Überschrift, Groß- und Kleinschreibung egal).
- Quelle 2: ein Plugin. `legacy-status` liest `.specify/feature-status.yml` (`feature_status_report.specs[].status: descoped`). Quellen sind damit konfigurierbar (`plugins:` und deren `options`), nicht fest verdrahtet.
- Eine zurückgestellte Spec hat keine Station und erzeugt weder `approval`, `clarification` noch `operator_task`.

**Plugins (`plugins:` in der Config)**

- Ein Plugin liefert zurückgestellte Specs, blockierte Specs und Aufmerksamkeitseinträge. Es läuft bei jedem Board-Aufbau, vor der Spec-Ableitung.
- Ein Fehler in einem Plugin bringt das Board nie zum Absturz: Das Plugin liefert dann nichts und ein Hinweis in `notes` nennt den Grund. Ungültige Einträge eines Plugins werden wie andere ungültige Listeneinträge verworfen und gemeldet.
- `legacy-status` (Optionen `blockers_file`, `decisions_file`, `status_file`; Pfade im Projekt): `.specify/blockers.yml` setzt `blocked` für jeden Eintrag, ein `blocker`-Eintrag entsteht nur bei `actionable: blocked` oder `partial`. `.specify/deferred-decisions.md` erzeugt je offener Frage (Abschnitt „Offen“) einen Eintrag `decision`. Fehlende Dateien ergeben einen Hinweis.

**Ticker und Zeiten**

- Jeder Ticker-Eintrag trägt `commit` (kurzer Hash, 7 Zeichen). Der Betreff (`text`) erscheint nur mit `share_commit_subjects: true` oder lokal.
- Die Textausgabe `sak board --text` zeigt die Zeit lokal mit Zone, zum Beispiel `2026-10-21 14:03 UTC+02:00`. Im Board-Dokument bleiben alle Zeiten RFC 3339.

**Bewusste Abweichungen vom alten ImmoAgent-Board**

| Thema | Altes Board | Kit | Wirkung (ImmoAgent) |
|---|---|---|---|
| Task-Zeile | nur `- [ ] T123` (mit ID, nur `-`) | jede Aufzählung mit Checkbox, ID egal | andere Task-Zahlen bei 037, 038, 041, 063 |
| Fertig | Status `done`: alle Tasks mit ID erledigt | Station ab `implemented` und 0 offene, 0 teilweise Tasks | 63 statt 61 (037 und 041 hatten keine Task-IDs) |
| In Arbeit | Status `partial` | Station `implementing`, oder fertige Station mit Resttasks (066 bleibt `deployed`, zählt aber als in Arbeit) | gleiche Zahl (16) |
| `[~]` | eigener Zähler; 0 offen und teilweise ergibt `descoped` | eigenes Feld `tasks.partial`, verhindert „fertig“; `descoped` nur aus den Quellen oben | 018, 048 bleiben in Arbeit |
| Blockiert | Specs mit Eintrag in `blockers.yml` | gleich, über das Plugin | 4 und 4 |
| Entscheidung | offene Zeilen in `deferred-decisions.md` | gleich, über das Plugin | 0 und 0 |
| Freigabe | Status `not-started` (keine Task erledigt) | Tasks vorhanden, keine erledigt, nie ein Lauf gestartet | 084, 085, 088 warten nach dem Import der Läufe nicht mehr auf Freigabe |
| Betreiber-Aufgabe | keine Einträge | je offene Task mit Marker außerhalb von Code-Spans | 9 zusätzliche Einträge (092, 093) |
| Zeit im Text | UTC ohne Kennzeichnung | lokale Zeit mit Zone | |

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
- `sak board serve` bindet nur 127.0.0.1, ohne `SO_REUSEADDR` (Windows), ohne `--port` wird 5192 und bei Belegung der nächste freie Port bis 5212 genommen (Spec 009); ein ausdrücklich gewählter, belegter Port ergibt Exit 2. `metrics.blocked` ist in v1 immer 0.

**Dashboard (007)**

- Die API wird mit esbuild gebündelt (`apps/dashboard-api/scripts/build.mjs`), weil `@sak/contracts` TypeScript-Quellen exportiert; `tsc` läuft nur als `lint`. Nur `better-sqlite3` bleibt extern.
- Tailwind v4 (`@tailwindcss/vite`): kein `tailwind.config.ts`, die Tokens stehen in `src/index.css`. Die shadcn-Bausteine sind von Hand eingecheckt.
- Passwort-Hash im Format `scrypt:N:r:p:salt:hash` (ohne `$`); Projekt-Schlüssel `sak_<43 Zeichen base64url>`.
- Das Projekt ergibt sich aus dem Bearer-Schlüssel; abweichendes `project` in der Hülle ergibt 403. Retention gilt für den Event-Zeitstempel `ts`.
- Warnungen `idle` und `no_push_24h` des Portfolios sind kein Vokabular; die Texte stehen in der UI (`ProjectCard.tsx`).
- Tab `operator` aus dem frühen Konzept entfällt, es gelten `board|runs|attention|conflicts`. `conflicts` ist in v1 ein Hinweis (siehe [dashboard-concept](ui/dashboard-concept.md)).
- Playwright-E2E (Port 3100, frische DB) läuft nur lokal. Das Image wird auf dem VPS gebaut und läuft dort seit 2026-10-20.

**Robustheit aus dem ImmoAgent-Trial (Spec 011, Kit 0.2.0)**

- Prüfer-Integrität: `sak run snapshot` hält zusätzlich die Top-Level-Ordner fest, die Git nicht sieht (leere Ordner; ignorierte Ordner, `guard.clean_ignore` und selbst ignorierende Werkzeug-Caches zählen nicht). `reviewer-check` nennt neue Ordner. `sak run cleanup <run>` entfernt Links und Junctions unter `runs/<id>/`, ohne ihnen zu folgen; `abort` und `combine` rufen es selbst auf. `init` schlägt `guard.clean_ignore`-Einträge für erkannte Testwerkzeuge vor (Regeln in `templates/config/detectors.json`, Option `--clean-ignore`), damit der Kern frei von Werkzeugnamen bleibt.
- Worktrees: Die Engine erkennt einen verknüpften Worktree an der `.git`-Datei samt `commondir`. Fehlende `dashboard.url`/`dashboard.push` und der Schlüssel (`dashboard.key`) kommen aus dem Haupt-Checkout; eigene Werte des Worktrees haben Vorrang, die Umgebungsvariable geht vor. Die Hooks schreiben weiterhin nach `CLAUDE_PROJECT_DIR`; `preflight` warnt, wenn die Sitzung nicht im Checkout des Laufs läuft. Von sak verwaltete Worktrees folgen mit der Spec „Parallelbetrieb“.
- Testbefehle: `init` liest `pyproject.toml` und schlägt `--extra <x>` bzw. `--group <g>` vor (nur Vorschlag, übergebene Befehle bleiben). Eine Gruppe, die uv standardmäßig lädt (`dev` bzw. `tool.uv.default-groups`), braucht nichts. `doctor` prüft die Auffindbarkeit der Programme aus `commands.*`; `--probe-commands` führt pytest mit `--collect-only -q` (60 s) und andere bekannte Werkzeuge mit `--version` aus, `commands.prepare` nie.
- Settings: Das Lock führt optional `settings_allow` (vom Kit eingetragene allow-Regeln, rückwärtskompatibel in `sak.lock/1`). Beim Upgrade werden genau diese ersetzt, fremde bleiben. Bei einem Lock ohne das Feld (Altbestand) gelten nur bekannte Kit-Muster (die früheren `git switch *` und `git merge *` und die Einträge des aktuellen Fragments) als Kit-eigen; frühere Testbefehle des Kits bleiben dann stehen und werden ab dem nächsten Upgrade verwaltet. Der Plan listet alle Regeln einzeln und nennt den Geltungsbereich (das ganze Projekt).
- Kompaktieren: Der Hook `SessionStart` (Matcher `compact`) ruft `sak hook session-start`. Er gibt nur bei `source == "compact"` und aktivem Lauf JSON mit `hookSpecificOutput.additionalContext` aus (Lauf-ID, Spec, Zustand, Runde, Rollen, Muss-Befunde der letzten Prüfung, nächster Schritt), endet immer mit Exit 0 und gibt nach 1,8 s still auf. Das Kit empfiehlt nie, den Kontext zu kompaktieren.
- Dashboard: `dashboard status` und `doctor` melden erst mit vorhandenem Schlüssel ok; `status` ist bei `last_error` nicht ok (Exit 1). Ein 403 `project mismatch` nennt das gesendete und, falls das Dashboard es liefert (`expected`), das erwartete Projekt, nie einen Schlüssel.

**Autonomie-Stufen (Spec 012, Kit 0.3.0)**

- Config: `autonomy: {push: manual|after_merge, deploy: after_approval|never, remote: origin}` in `sak.config/1` (optional, Defaults streng). Die Engine liest die Stufe aus `ctx.cfg.data["autonomy"]`; der Orchestrator-Skill liest sie aus `sak config show`.
- `sak run push <lauf>` (`pipeline/commands.py`, `pipeline/git.py::push_branch`): nur `git push <remote> <basis>:<basis>`, `push.followTags=false`, `GIT_TERMINAL_PROMPT=0`, Timeout 60 s, URLs ohne Zugangsdaten in Meldungen. Der Remote-Name darf nicht mit `-` beginnen. Der Merge-Commit steht seit 0.3.0 auch in der `run.json` (ältere Läufe: aus dem Ereignis `run.merged`).
- Vertrag: Ereignis `run.pushed` mit `data: {remote, branch, commit}`; kein neuer Lauf-Zustand (`merged` bleibt). Board-Feld `runs[].pushed` (nur gesetzt, wenn ein `run.pushed` vorliegt).
- „Push abgelehnt“ (non-fast-forward): `run.escalated` mit Gate `release` ohne Zustandswechsel. Die Board-Ableitung hält diese Eskalation an einem `merged`-Lauf offen und listet sie als Aufmerksamkeit der Art `escalation`, bis ein späteres `run.pushed` sie schließt. Andere Fehler (Netz, Zugang, Zeitlimit) lehnen nur ab.
- Die Deny-Regel `Bash(git push)` im Settings-Fragment bleibt. Der Push über `sak` ist durch die Allowlist `… sak *` gedeckt.
