# Feature Specification: Lokale Bedienung und Betrieb

**Feature Branch**: `009-local-ops`

**Created**: 2026-10-20

**Status**: Draft

**Input**: Befunde aus dem ersten Einsatz am 2026-10-20 (Pilot AI-Forge, Deployment specboard.prozessfit.de):
- `uv` war in einer offenen Shell nicht im PATH.
- Port 5192 war durch das ImmoAgent-Board belegt.
- Das lokale Dashboard und die Anbindung eines Projekts brauchten rund 10 Einzelbefehle.
- Der Deploy auf dem VPS lief per Hand.
- Die Portfolio-Karte ist nur über den Titel anklickbar und zeigt zu wenig.
- Kleinere Deploy-Mängel: Node-Warnung `MODULE_TYPELESS_PACKAGE_JSON`, keine `.dockerignore`.

## Clarifications

### Session 2026-10-20

- Q: Wie soll die Portfolio-Karte bedienbar sein? → A: Die ganze Karte hat einen Hover-Zustand und ist als Ganzes anklickbar, nicht nur das Label (Betreiber).
- Q: Layout auf dem Desktop? → A: Die volle Breite nutzen; aktuell bleibt rechts viel Fläche leer (Betreiber, US5 Szenario 5).

## User Scenarios & Testing *(mandatory)*

### User Story 1 – `sak` funktioniert ohne PATH-Wissen (Priority: P1)

Im Zielprojekt startet `.spec-agent\sak board serve` (Windows) bzw. `.spec-agent/sak board serve` (POSIX), auch wenn `uv` nicht im PATH der aktuellen Shell steht.

**Acceptance Scenarios**:
1. **Given** uv ist per WinGet installiert, aber nicht im PATH der Shell, **When** `.spec-agent\sak version` läuft, **Then** findet der Starter uv an einem bekannten Ort und gibt die Kit-Version aus.
2. **Given** uv ist gar nicht installiert, **When** der Starter läuft, **Then** endet er mit Exit 127 und nennt den passenden Installationsbefehl für die Plattform.

### User Story 2 – Lokales Board startet immer (Priority: P1)

`sak board serve` weicht bei belegtem Default-Port auf den nächsten freien Port aus und nennt die URL. `--open` öffnet den Browser.

**Acceptance Scenarios**:
1. **Given** Port 5192 ist belegt, **When** `sak board serve` ohne `--port` läuft, **Then** lauscht der Server auf dem ersten freien Port zwischen 5193 und 5212 und gibt die URL aus.
2. **Given** `--port 5192` ist ausdrücklich gesetzt und belegt, **When** der Befehl läuft, **Then** folgt Exit 2 mit klarer Meldung, ohne Ausweichen.

### User Story 3 – Lokales Portfolio-Dashboard mit einem Befehl (Priority: P2)

Im Kit-Repo startet `pnpm dashboard:local` das zentrale Dashboard lokal unter `http://127.0.0.1:3000`. Beim ersten Start legt der Befehl Secrets und Datenbank unter `.local/` an (gitignored) und fragt einmal ein lokales Admin-Passwort ab. `pnpm dashboard:project add <key> <name>` legt Projekte an.

**Acceptance Scenarios**:
1. **Given** ein frischer Checkout, **When** `pnpm dashboard:local` läuft, **Then** wird bei Bedarf gebaut, `.local/dashboard.env` wird mit Session-Secret, DB-Pfad und Web-Pfad angelegt, das Passwort einmal abgefragt (nur der Hash wird gespeichert), und der Server startet im Entwicklungsmodus.
2. **Given** `.local/dashboard.env` existiert, **When** der Befehl erneut läuft, **Then** startet er ohne Rückfragen.

### User Story 4 – Projekt mit einem Befehl anbinden (Priority: P1)

Im Zielprojekt schreibt `sak dashboard connect --url <url>` den Projekt-Schlüssel und trägt die URL in die Config ein. Der Schlüssel kommt verdeckt aus der Eingabe oder per `--key-stdin`. Danach folgt ein Test-Push.

**Acceptance Scenarios**:
1. **Given** keine `dashboard.key`, **When** `sak dashboard connect --url https://x --key-stdin --yes` mit Schlüssel auf stdin läuft, **Then** liegt der Schlüssel in `.spec-agent/dashboard.key`, die URL steht in `config.yml` mit erhaltenen Kommentaren, `config check` ist ok, und das Ergebnis des Test-Pushs wird gemeldet.
2. **Given** ohne `--yes`, **When** der Befehl läuft, **Then** zeigt er nur den Plan: Config-Diff und Schlüsseldatei neu oder ersetzt. Er schreibt nichts (Constitution III).
3. **Given** eine bestehende `dashboard.key`, **When** ohne `--force` verbunden wird, **Then** folgt eine Ablehnung.
4. **Given** der Schlüssel hat nicht das Format `sak_` + 43 Zeichen base64url, **When** verbunden wird, **Then** folgt eine Ablehnung. Der Schlüssel erscheint nie in einer Ausgabe.

### User Story 5 – Portfolio-Karte: anklickbar, mit Hover, aussagekräftig (Priority: P1)

**Acceptance Scenarios**:
1. **Given** das Portfolio, **When** die Maus über einer Karte steht, **Then** zeigt die Karte einen Hover-Zustand: Rahmen oder Schatten hervorgehoben, Cursor Pointer, Hinweis „Board öffnen →“.
2. **Given** ein Klick irgendwo auf die Karte, außer auf innere Links, **When** geklickt wird, **Then** öffnet sich `#/project/<key>`. Innere Links (Eskalation, Lauf) führen weiter zu ihrem Ziel. Mittelklick oder Strg+Klick öffnet einen neuen Tab.
3. **Given** Tastaturbedienung, **When** mit Tab navigiert wird, **Then** ist die Karte fokussierbar, hat einen sichtbaren Fokusrahmen und öffnet sich mit Enter.
4. **Given** ein Projekt mit Board, **When** die Karte erscheint, **Then** zeigt sie zusätzlich:
   - einen Balken mit der Verteilung der Specs über die Stationen, mit Tooltip pro Segment
   - die Zahl der fertigen Specs
   - die ersten 3 Aufmerksamkeitseinträge (Art und Spec) plus „+N weitere“
   - den letzten Deploy- bzw. Verified-Marker

5. **Given** ein Desktop-Fenster (≥ 1280 px), **When** das Portfolio, ein Projekt oder ein Lauf angezeigt wird, **Then** nutzt das Layout die volle Fensterbreite (nur seitlicher Innenabstand, keine schmale feste Maximalbreite). Portfolio-Karten füllen die Zeile responsiv (z. B. `repeat(auto-fill, minmax(340px, 1fr))`). Bei sehr breiten Fenstern (≥ 2200 px) ist eine großzügige Obergrenze erlaubt, damit Textzeilen lesbar bleiben.

### User Story 6 – Dashboard-Deploy per Skript (Priority: P2)

`deploy/dashboard/deploy-vps.sh` überträgt den committeten Stand (`git archive`) per SSH, baut das Image auf dem VPS, startet per `docker compose up -d`, wartet auf `healthy` und prüft `/healthz`. Die Zugangsdaten stehen in `deploy/dashboard/vps.env` (gitignored, Vorlage `vps.env.example`). `.env` auf dem VPS und Caddy fasst das Skript nie an.

**Acceptance Scenarios**:
1. **Given** ein unsauberer Arbeitsstand, **When** das Skript läuft, **Then** bricht es ab. `--dry-run` zeigt die Schritte, ohne etwas auszuführen.
2. **Given** der Build schlägt fehl, **When** das Skript läuft, **Then** läuft der alte Container weiter, und das Skript endet mit dem Build-Log-Ausschnitt.
3. **Given** `--prune`, **When** das Skript erfolgreich war, **Then** wird der Build-Cache auf 5 GB begrenzt (`docker builder prune --keep-storage 5GB`).

### User Story 7 – Kleine Deploy-Mängel (Priority: P3)

- Die Runtime-Stage setzt `"type": "module"`, die Node-Warnung entfällt.
- `.dockerignore` mit `**/node_modules`, `**/dist`, `.git`, `.local`, `**/e2e/screenshots`.

## Requirements *(mandatory)*

- **FR-001**: Init und Upgrade MÜSSEN `.spec-agent/sak.cmd` und `.spec-agent/sak` als verwaltete Dateien installieren (Lock, Upgrade-Regeln aus Spec 005). Die POSIX-Datei wird ausführbar angelegt.
- **FR-002**: Die Starter MÜSSEN uv in dieser Reihenfolge suchen: Umgebungsvariable `SAK_UV`, PATH, dann die bekannten Orte.
  - Windows: `%LOCALAPPDATA%\Microsoft\WinGet\Links\uv.exe`, `%LOCALAPPDATA%\Microsoft\WinGet\Packages\astral-sh.uv_*\uv.exe`, `%USERPROFILE%\.local\bin\uv.exe`, `%USERPROFILE%\.cargo\bin\uv.exe`
  - POSIX: `~/.local/bin/uv`, `~/.cargo/bin/uv`, `/opt/homebrew/bin/uv`, `/usr/local/bin/uv`

  Danach rufen sie `uv run --project <ordner des starters>/engine sak %*` bzw. `"$@"` auf und reichen den Exit-Code durch.
- **FR-003**: Die Hooks im Settings-Fragment bleiben unverändert. Hooks laufen in der Umgebung von Claude Code.
- **FR-004**: `sak board serve` MUSS das Port-Ausweichen aus US2 und `--open` umsetzen (Standardbibliothek `webbrowser`).
- **FR-005**: `sak dashboard connect` MUSS US4 umsetzen.
  - Die Config wird zeilenbasiert geändert: nur die `url:`-Zeile im Block `dashboard:`, Kommentare bleiben erhalten. Danach wird die Datei mit dem Schema geprüft. Ist sie ungültig, wird zurückgerollt.
  - Die Schlüsseldatei wird mit Rechten 600 (POSIX) angelegt.
  - `sak dashboard status` zeigt URL, ob ein Schlüssel vorhanden ist (nie den Schlüssel selbst), Push-Modus, Cursor und letzten Push-Fehler.
- **FR-006**: `pnpm dashboard:local` und `pnpm dashboard:project` MÜSSEN US3 umsetzen. Sie laufen als plattformneutrales Node-Skript. `.local/` steht in der Wurzel-`.gitignore`. Der Server lauscht im lokalen Modus nur auf `127.0.0.1`.
- **FR-007**: Die Portfolio-Karte MUSS US5 umsetzen. Die zusätzlichen Daten liefert `GET /api/portfolio`, abgeleitet aus dem gespeicherten Board: `stage_counts`, `done`, `attention_preview[≤3]`, `attention_total`, `last_marker`. Klick und Fokus funktionieren über ein „stretched link“-Muster (eine semantische `<a>`, innere Links liegen darüber). Ein `div` mit onClick wird nicht verwendet.
- **FR-008**: `deploy/dashboard/deploy-vps.sh` MUSS US6 umsetzen. Es ist Bash und läuft unter Git Bash und Linux. `vps.env` steht in `.gitignore`. Das Skript führt nichts mit `rm -rf` außerhalb von `REMOTE_DIR/src*` aus.
- **FR-009**: US7.
- **FR-010**: Die Doku MUSS aktualisiert werden: README (Schnellstart lokal, Starter, connect, deploy), `deploy/dashboard/README.md`, `docs/follow-ups.md` (erledigte Punkte streichen).

## Success Criteria *(mandatory)*

- **SC-001**: Vom frischen Checkout bis zu „Projekt erscheint im lokalen Portfolio“ sind es höchstens 4 Befehle: `pnpm dashboard:local`, `pnpm dashboard:project add …`, `sak dashboard connect …`, `sak push`.
- **SC-002**: Die Portfolio-Karte ist per Maus (ganze Fläche) und Tastatur bedienbar. Das zeigt ein Playwright-Test einschließlich Hover-Screenshot.
- **SC-003**: Ein Dashboard-Update auf dem VPS ist ein einziger Befehl: `deploy/dashboard/deploy-vps.sh`.

## Assumptions

- Die Starter sind keine Engine-Logik. Sie liegen als Vorlagen unter `packages/agent-blueprint/templates/spec-agent/` und werden über Init und Upgrade verwaltet.
