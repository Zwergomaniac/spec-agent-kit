# Dashboard-Deployment

Ein Container (`spec-agent-dashboard`): Node-Prozess mit Hono-API und gebauter UI auf Port 3000, SQLite unter `/data`.
Caddy läuft extern (edge-caddy) und gehört nicht zu diesem Repo. `caddy.example` ist nur ein Beispiel.

## Image bauen

Im Repo-Root (Docker wird für den Build benötigt):

```sh
docker build -f deploy/dashboard/Dockerfile -t spec-agent-dashboard:latest .
```

## Update per Skript

Nach der Erstinstallation aktualisiert `deploy/dashboard/deploy-vps.sh` das Dashboard (Bash, läuft unter Git Bash und Linux):

```sh
cp deploy/dashboard/vps.env.example deploy/dashboard/vps.env   # einmal; vps.env ist gitignoriert, nie committen
# VPS_HOST, VPS_USER, VPS_PORT, VPS_SSH_KEY, REMOTE_DIR, COMPOSE_PROJECT, COMPOSE_SERVICE, COMPOSE_FILE anpassen

deploy/dashboard/deploy-vps.sh --dry-run           # Trockenlauf
deploy/dashboard/deploy-vps.sh                     # echtes Update
deploy/dashboard/deploy-vps.sh --prune             # danach Build-Cache aufräumen
deploy/dashboard/deploy-vps.sh --env-file <pfad>   # andere Zugangsdaten
```

Ablauf: `git archive HEAD` auf den VPS übertragen, dort das Image bauen (der laufende Container bleibt bis dahin unberührt; bei Fehlern steht das Ende des Build-Logs in der Ausgabe), Quelltext umschalten, `docker compose up -d --no-deps <Dienst>`, bis zu 60 s auf `healthy` warten und `/healthz` prüfen. Deployt wird nur `HEAD`; bei unsauberem Arbeitsstand bricht ein echter Lauf ab. `vps.env` enthält nur Zugangsdaten zum VPS. Die `.env` des Dashboards und die Caddy-Konfiguration fasst das Skript nie an, gelöscht wird nur unter `$REMOTE_DIR/src*`.

## Konfiguration (nur Umgebungsvariablen)

| Variable | Pflicht | Default | Bedeutung |
|---|---|---|---|
| `SAK_ADMIN_PASSWORD_HASH` | ja | – | scrypt-Hash des Admin-Passworts |
| `SAK_SESSION_SECRET` | ja | – | mindestens 32 zufällige Zeichen, signiert die Session-Cookies |
| `SAK_DB_PATH` | nein | `/data/dashboard.db` | SQLite-Datei (WAL) |
| `SAK_RETENTION_DAYS` | nein | `30` | Events älter als diese Frist werden täglich gelöscht, Boards bleiben |
| `SAK_TRUST_PROXY` | nein | `true` | Client-IP aus `X-Forwarded-For` (letzter Eintrag, vom Proxy gesetzt) |
| `PORT` | nein | `3000` | Port im Container |

Fehlt ein Pflicht-Secret, verweigert der Start mit einer klaren Meldung.
Das Session-Cookie ist `Secure`; nur mit `NODE_ENV=development` entfällt das Flag (lokale Entwicklung ohne TLS).

## Secrets erzeugen

```sh
# Session-Secret
openssl rand -base64 48

# Admin-Passwort-Hash (Passwort wird ohne Echo abgefragt, mindestens 12 Zeichen)
docker run --rm -it spec-agent-dashboard:latest node apps/dashboard-api/dist/cli/hash-password.js
```

Beides in die `.env` neben der Compose-Datei eintragen. Der Hash hat das Format `scrypt:N:r:p:salt:hash` und enthält kein `$`, braucht also kein Escaping.

## Erstinstallation auf dem VPS

Einmalig, bevor das Skript greift (`REMOTE_DIR` aus `vps.env`):

1. Compose-Datei: den Inhalt von `compose.snippet.yml` in die Compose-Datei in `REMOTE_DIR` übernehmen (bei einer bestehenden Datei Dienst, Volume und Netz ergänzen). Das Skript erwartet standardmäßig `docker-compose.yml`; heißt die Datei `compose.yml`, `COMPOSE_FILE=compose.yml` in `vps.env` setzen.
2. `.env` neben der Compose-Datei mit `SAK_EDGE_NETWORK` (Name des Netzes von edge-caddy, `docker network ls`), `SAK_SESSION_SECRET` und `SAK_ADMIN_PASSWORD_HASH`. Beide Secrets erzeugt und setzt der Betreiber selbst (siehe „Secrets erzeugen“); sie gehören nie ins Repo.
3. Erstes Image bauen und starten, zum Beispiel mit `deploy-vps.sh` (setzt Compose-Datei und `.env` voraus).
4. Caddy anpassen (nächster Abschnitt).

### Caddy anpassen

Die Caddyfile ist als Einzeldatei in den Caddy-Container gemountet. Ersetzt man die Datei, bekommt sie einen neuen Inode und der Container sieht weiter die alte. Deshalb den Block aus `caddy.example` (Host angepasst) an die vorhandene Datei **anhängen** und die Datei nicht ersetzen:

```sh
cp Caddyfile Caddyfile.bak                                             # Backup
cat block.txt >> Caddyfile                                             # anhängen
docker exec <caddy-container> caddy validate --config /etc/caddy/Caddyfile
docker exec <caddy-container> caddy reload --config /etc/caddy/Caddyfile
```

Containername und Pfad der Caddyfile hängen vom VPS ab. Schlägt `validate` fehl, den Inhalt aus dem Backup in dieselbe Datei zurückschreiben (`cat Caddyfile.bak > Caddyfile`). Caddy gehört nicht zu diesem Repo.

## Starten

`compose.snippet.yml` in die vorhandene Compose-Datei übernehmen. Der Name des externen Netzes von edge-caddy kommt aus `SAK_EDGE_NETWORK` (Default `edge`). Heißt das Netz auf dem VPS `edge-network`, muss `SAK_EDGE_NETWORK=edge-network` in der `.env` neben der Compose-Datei gesetzt sein (Netzname prüfen mit `docker network ls`). Danach in `caddy.example` den Host anpassen und den Block in die Caddy-Konfiguration übernehmen.

Prüfen: `GET /healthz` liefert `{"status":"ok"}`.

## Projekt anlegen

Über die UI (`#/admin`, Anmeldung nötig) oder per CLI im Container. Der Projekt-Schlüssel wird genau einmal angezeigt.

```sh
docker exec spec-agent-dashboard node apps/dashboard-api/dist/cli/project.js add immo-agent ImmoAgent
docker exec spec-agent-dashboard node apps/dashboard-api/dist/cli/project.js list
docker exec spec-agent-dashboard node apps/dashboard-api/dist/cli/project.js rotate immo-agent
docker exec spec-agent-dashboard node apps/dashboard-api/dist/cli/project.js remove immo-agent
```

Der Schlüssel kommt als `Authorization: Bearer <schlüssel>` in den Push des Zielprojekts (`POST /api/ingest`).

## Betrieb

- Das Dashboard wird vor den Projekten aktualisiert (Spec 002 FR-008).
- Backup: das Volume `/data` (SQLite, WAL). Es enthält nur Metadaten.
- Der Container läuft als Nutzer `node` (nicht root).
- Build-Cache begrenzen: Jeder Build auf dem VPS erzeugt Cache, dort lief die Platte schon mit 50 GB davon voll. `deploy-vps.sh --prune` begrenzt den Cache nach dem Deploy auf 5 GB. Eine dauerhafte Grenze über `daemon.json` ist offen (siehe [docs/follow-ups.md](../../docs/follow-ups.md)).
