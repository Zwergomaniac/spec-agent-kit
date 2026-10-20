#!/usr/bin/env bash
# Dashboard-Deploy auf den VPS (Spec 009 US6).
#   deploy/dashboard/deploy-vps.sh [--dry-run] [--prune] [--env-file <pfad>]
# Ablauf: git archive HEAD -> SSH -> Image auf dem VPS bauen -> docker compose up -d -> auf "healthy" warten -> /healthz prüfen.
# Zugangsdaten: deploy/dashboard/vps.env (gitignored, Vorlage vps.env.example).
# Das Skript fasst die .env auf dem VPS und Caddy nie an und löscht nur unter $REMOTE_DIR/src*.
set -euo pipefail

DRY_RUN=0
PRUNE=0
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$HERE/vps.env"

usage() { sed -n '2,6p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
die() { echo "Fehler: $*" >&2; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --prune) PRUNE=1 ;;
    --env-file) shift; [ $# -gt 0 ] || die "--env-file braucht einen Pfad"; ENV_FILE="$1" ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; die "Unbekannte Option: $1" ;;
  esac
  shift
done

[ -f "$ENV_FILE" ] || die "$ENV_FILE fehlt (Vorlage: deploy/dashboard/vps.env.example)"
# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

: "${VPS_HOST:?VPS_HOST fehlt in vps.env}"
: "${VPS_USER:?VPS_USER fehlt in vps.env}"
: "${REMOTE_DIR:?REMOTE_DIR fehlt in vps.env}"
VPS_PORT="${VPS_PORT:-22}"
VPS_SSH_KEY="${VPS_SSH_KEY:-}"
COMPOSE_PROJECT="${COMPOSE_PROJECT:-}"
COMPOSE_SERVICE="${COMPOSE_SERVICE:-spec-agent-dashboard}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.yml}"

# Alle Werte landen in einem Remote-Befehl. Deshalb nur harmlose Zeichen zulassen, und REMOTE_DIR muss
# ein absoluter Pfad mit mindestens zwei Ebenen sein, damit "rm -rf $REMOTE_DIR/src*" nie außerhalb landet.
safe() { [[ "$2" =~ ^[A-Za-z0-9._@:/-]+$ ]] || die "$1 enthält ungültige Zeichen"; }
safe VPS_HOST "$VPS_HOST"; safe VPS_USER "$VPS_USER"; safe REMOTE_DIR "$REMOTE_DIR"
safe COMPOSE_SERVICE "$COMPOSE_SERVICE"; safe COMPOSE_FILE "$COMPOSE_FILE"
[ -z "$COMPOSE_PROJECT" ] || safe COMPOSE_PROJECT "$COMPOSE_PROJECT"
[[ "$VPS_PORT" =~ ^[0-9]+$ ]] || die "VPS_PORT muss eine Zahl sein"
[[ "$REMOTE_DIR" =~ ^/[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+$ ]] || die "REMOTE_DIR muss ein absoluter Pfad mit mindestens zwei Ebenen sein"
[[ "$REMOTE_DIR" != *..* ]] || die "REMOTE_DIR darf kein .. enthalten"
REMOTE_DIR="${REMOTE_DIR%/}"

cd "$HERE/../.."
git rev-parse --git-dir >/dev/null 2>&1 || die "Kein Git-Repository"
if ! git diff --quiet || ! git diff --cached --quiet; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "Hinweis: Arbeitsstand ist nicht sauber (ein echter Lauf würde hier abbrechen)." >&2
  else
    die "Arbeitsstand ist nicht sauber. Erst committen oder verwerfen; deployt wird nur HEAD."
  fi
fi
SHA="$(git rev-parse --short=12 HEAD)"

SSH_OPTS=(-p "$VPS_PORT" -o BatchMode=yes)
[ -z "$VPS_SSH_KEY" ] || SSH_OPTS+=(-i "$VPS_SSH_KEY")
TARGET="$VPS_USER@$VPS_HOST"
SRC="$REMOTE_DIR/src"
COMPOSE=(docker compose)
[ -z "$COMPOSE_PROJECT" ] || COMPOSE+=(-p "$COMPOSE_PROJECT")
COMPOSE+=(-f "$REMOTE_DIR/$COMPOSE_FILE")
COMPOSE_STR="${COMPOSE[*]}"

step() { echo; echo "==> $*"; }
# Führt einen Remote-Skript von stdin aus bzw. zeigt es im Trockenlauf.
remote() {
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] ssh ${SSH_OPTS[*]} $TARGET bash -s <<'REMOTE'"; cat; echo "REMOTE"
  else
    ssh "${SSH_OPTS[@]}" "$TARGET" bash -s
  fi
}

echo "Deploy von $SHA nach $TARGET:$REMOTE_DIR (Dienst $COMPOSE_SERVICE)"
[ "$DRY_RUN" -eq 0 ] || echo "Trockenlauf: es wird nichts ausgeführt."

step "1/5 Quelltext übertragen (git archive HEAD)"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "[dry-run] git archive --format=tar HEAD | ssh ${SSH_OPTS[*]} $TARGET 'rm -rf $SRC.new && mkdir -p $SRC.new && tar -x -C $SRC.new'"
else
  git archive --format=tar HEAD | ssh "${SSH_OPTS[@]}" "$TARGET" "rm -rf $SRC.new && mkdir -p $SRC.new && tar -x -C $SRC.new"
fi

step "2/5 Image auf dem VPS bauen (der laufende Container bleibt unberührt)"
remote <<REMOTE
set -euo pipefail
cd $SRC.new
if ! docker build -f deploy/dashboard/Dockerfile -t spec-agent-dashboard:latest -t spec-agent-dashboard:$SHA . > $REMOTE_DIR/build.log 2>&1; then
  echo "Build fehlgeschlagen, der alte Container läuft weiter. Ende des Build-Logs:" >&2
  tail -n 40 $REMOTE_DIR/build.log >&2
  exit 1
fi
echo "Image spec-agent-dashboard:$SHA gebaut."
REMOTE

step "3/5 Quelltext umschalten (src.new -> src, alter Stand als src.prev)"
remote <<REMOTE
set -euo pipefail
rm -rf $SRC.prev
if [ -d $SRC ]; then mv $SRC $SRC.prev; fi
mv $SRC.new $SRC
REMOTE

step "4/5 Dienst neu starten (docker compose up -d, nur $COMPOSE_SERVICE)"
remote <<REMOTE
set -euo pipefail
cd $REMOTE_DIR
$COMPOSE_STR up -d --no-deps $COMPOSE_SERVICE
REMOTE

step "5/5 Auf healthy warten (höchstens 60 s) und /healthz prüfen"
remote <<REMOTE
set -euo pipefail
cid=\$($COMPOSE_STR ps -q $COMPOSE_SERVICE)
[ -n "\$cid" ] || { echo "Container nicht gefunden." >&2; exit 1; }
status=starting
for _ in \$(seq 1 30); do
  status=\$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "\$cid")
  [ "\$status" = healthy ] && break
  sleep 2
done
if [ "\$status" != healthy ]; then
  echo "Dienst wurde nicht healthy (Status: \$status). Letzte Logzeilen:" >&2
  docker logs --tail 30 "\$cid" >&2 || true
  exit 1
fi
docker exec "\$cid" node -e "fetch('http://127.0.0.1:'+(process.env.PORT||3000)+'/healthz').then(r=>r.json()).then(j=>{console.log('healthz:',JSON.stringify(j));process.exit(j.status==='ok'?0:1)}).catch(e=>{console.error(e.message);process.exit(1)})"
REMOTE

if [ "$PRUNE" -eq 1 ]; then
  step "Aufräumen: Build-Cache auf 5 GB begrenzen"
  remote <<'REMOTE'
set -euo pipefail
docker builder prune -f --keep-storage 5GB
REMOTE
fi

echo
if [ "$DRY_RUN" -eq 1 ]; then echo "Trockenlauf beendet."; else echo "Deploy von $SHA abgeschlossen."; fi
