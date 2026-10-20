# Tasks: Init- und Upgrade-CLI

**Input**: [spec.md](spec.md), [plan.md](plan.md), Specs 002–004 und 006, [../../docs/architecture.md](../../docs/architecture.md)

## Phase 1: Grundlagen

- [X] T001 `lock.schema.json` mit Beispielen, Generierung und Tests (Contracts-Workflow wie Spec 002).
  > Anmerkung: `upgraded_at` ist beim Erstinstallieren `null` (Pflichtfeld, nullable). Die Hashes sind SHA-256 über den Inhalt mit auf LF normalisierten Zeilenenden (autocrlf-fest). Ein `lock`-Eintrag fehlt in `common.schema.json`; `sha256` und `version` stehen lokal in `lock.schema.json`.
- [X] T002 `install/kit.py`, `install/lock.py`, `install/speckit.py`.
  > Anmerkung: Die Kit-Version steht in `packages/engine/src/spec_agent_kit/__init__.py` (`__version__`). `Kit.at(root)` liest sie dort; Tests nutzen dafür eine Kit-Kopie. Die Kit-Wurzel liegt fünf Ebenen über `install/kit.py` (der Plan nennt drei Ebenen ab dem Paketordner; gemeint ist dasselbe Verzeichnis).
- [X] T003 `templates/spec-agent/gitignore`.
  > Anmerkung: Zusätzlich zu `state/` und `dashboard.key` enthält die Vorlage `engine/.venv/` und `__pycache__/`, damit die vendorte Engine nach `uv sync`/Lauf keinen unsauberen Arbeitsstand erzeugt.
- [X] T004 Fixture-Ziel-Repo-Generator in `tests/install/conftest.py`.

## Phase 2: US1 – Init

- [X] T005 `install/settings.py` (FR-005) mit Tests: fehlende Datei, bestehende Hooks, bypass-Warnung, Idempotenz, ungültiges JSON.
- [X] T006 `install/plan.py` für init (FR-001 bis FR-003, FR-006), Validierung (FR-002).
  > Anmerkung (`--no-ui`): Ohne `--no-ui` ist `ui_review` aktiv und der Block `ui` bekommt die Platzhalter aus der Vorlage (`npx playwright test`, `http://127.0.0.1:5173`), dazu eine Warnung im Plan. Mit `--no-ui` bleibt `ui_review` aus.
  > Anmerkung (erneutes Init): Ein zweites `init` wird abgelehnt (Verweis auf `upgrade`) und ändert nichts. Das ist die Lesart von „idempotent“ für Init. Als „initialisiert“ gilt, wenn `.spec-agent/lock.json` existiert. Existiert nur eine `config.yml`, wird sie übersprungen (nie angefasst).
  > Anmerkung: Das Ziel muss die Git-Wurzel sein. Der Hinweis bei fehlendem spec-kit nennt `specify init --here --integration claude`. spec-kit-Version steht in `.specify/init-options.json` unter `speckit_version`. Testbefehle mit `{paths}` werden zu `Bash(… *)` in `permissions.allow`. `--allow-dirty` wird abgelehnt, wenn eine schreibende Aktion (create, merge, replace, delete oder die `.sak-new`-Datei) eine geänderte Datei berührt.
- [X] T007 `install/apply.py` und CLI `sak init`. Nach Apply: `uv sync` und `config check` (FR-009).
  > Anmerkung: `uv sync` läuft als `uv sync --project .spec-agent/engine --locked`; die Option `--no-sync` überspringt ihn. Der Plan erscheint als JSON auf stdout (Feld `text` enthält die Kurzfassung), die Kurzfassung steht zusätzlich auf stderr. Ein Exit-Code 1 nach `--apply` bedeutet: geschrieben ist alles, aber `uv sync` oder `config check` ist fehlgeschlagen (auch bei Konflikten mit eigenen Agents, deren Frontmatter nicht zur Config passt). Vor dem Schreiben prüft `apply` je Datei, ob das Ziel noch dem Planstand entspricht.
- [X] T008 Tests für US1 inklusive aller Acceptance Scenarios und SC-002.

## Phase 3: US2 – Upgrade

- [X] T009 Upgrade-Plan (replace, delete, conflict, skip) und Meldung neuer Config-Schlüssel. CLI `sak upgrade`.
  > Anmerkung („neue Config-Schlüssel“): Gemeldet werden alle Schlüssel der wirksamen Defaults, die in der Datei fehlen (oberste fehlende Ebene, mit Default-Wert). Ein Vergleich mit den Defaults der Vorversion gibt es nicht, weil das Lock keine Defaults speichert.
  > Anmerkung: Eine verwaltete Datei, die lokal fehlt, wird wiederhergestellt (`create`). Entfällt eine Kit-Datei und ist lokal geändert, bleibt sie samt Lock-Eintrag und wird bei jedem Upgrade als Warnung genannt. Ungelöste Konflikte werden bei jedem Upgrade erneut gemeldet (das Lock behält den alten Hash). Löst der Betreiber den Konflikt durch Übernahme der Kit-Fassung, übernimmt das nächste Upgrade den Stand ins Lock.
- [X] T010 Tests für US2 und Idempotenz (SC-001).

## Phase 4: US4 – Doctor

- [X] T011 `install/doctor.py` und CLI `sak doctor` mit Tests.
  > Anmerkung: Dashboard-Erreichbarkeit ist `GET <url>/healthz` (Timeout 3 s) und keine Pflichtprüfung. Lokal geänderte Dateien lassen die Lock-Prüfung bestehen (Hoheit des Zielprojekts), fehlende nicht. `engine` gilt als lauffähig, wenn der Aufruf aus genau dieser Engine kommt oder `.venv/pyvenv.cfg` existiert. Jeder Eintrag hat zusätzlich das Feld `required`. `sak doctor [ziel]` nimmt optional einen Zielpfad.

## Phase 5: US3 – Skill und Aufräumen

- [X] T012 `.claude/skills/sak-init/SKILL.md` im Kit-Repo: Fragen, Plan zeigen, nach Bestätigung `--apply`, doctor, nächste Schritte (Commit-Vorschlag, Dashboard-Projekt anlegen, Schlüssel in `.spec-agent/dashboard.key` oder Env).
  > Anmerkung: Der Skill ist nur `user-invocable` (`disable-model-invocation: true`) und liegt bewusst nicht unter `templates/`, wird also nicht in Zielprojekte installiert.
- [X] T013 Altes Gerüst entfernen (FR-010). `packages/agent-blueprint/AGENTS.md` neu schreiben.

## Phase 6: Abschluss

- [X] T014 Smoke-Test SC-003 in CI (Windows und Linux). Alles grün. README-Statusmatrix: Init-Skript → ersetzt durch `sak init` (implementiert), Upgrade-CLI und Agent-Skill → implementiert.
  > Anmerkung: Der CI-Job `smoke-init-upgrade` (Windows und Linux) läuft in `.github/workflows/ci.yml` gegen Wegwerf-Verzeichnisse mit einer Kit-Kopie. Dieselben Schritte wurden lokal (Git Bash, Windows 11) auch offline über den uv-Cache erfolgreich ausgeführt. Zusätzlich führt `tests/install/test_install_real_sync.py` einmal ein echtes `uv sync` aus.
