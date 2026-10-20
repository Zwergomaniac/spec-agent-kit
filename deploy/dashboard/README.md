# Dashboard-Deployment

Ein Container (`spec-agent-dashboard`): Node-Prozess mit Hono-API und gebauter UI auf Port 3000, SQLite unter `/data`.
Caddy läuft extern (edge-caddy) und gehört nicht zu diesem Repo. `caddy.example` ist nur ein Beispiel.

## Image bauen

Im Repo-Root (Docker wird für den Build benötigt):

```sh
docker build -f deploy/dashboard/Dockerfile -t spec-agent-dashboard:latest .
```

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
