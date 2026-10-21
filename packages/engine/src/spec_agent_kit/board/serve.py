"""Lokale Ansicht: ``sak board serve`` (Spec 006 FR-008, Spec 010 FR-001).

Nur ``127.0.0.1``, nur ``GET``, Host-Header-Prüfung gegen DNS-Rebinding. Der Server liefert die
gebaute Dashboard-UI aus ``board/web/`` (mit SPA-Fallback) und eine Lese-API, deren Antworten
dieselbe Form haben wie die des zentralen Dashboards (``apps/dashboard-api``), ohne Auth:

- ``GET /api/meta`` (zusätzlich ``mode: "local"`` und ``project_key``)
- ``GET /api/projects/<key>``: das Board, live gebaut und höchstens alle 2 s neu
- ``GET /api/projects/<key>/runs/<runId>``
- ``GET /api/projects/<key>/events?run=&since=&limit=``

Außerdem bleibt ``GET /board.json`` (das Board-Dokument) für Skripte erhalten. Fehlt ``board/web/``
(die UI wird bei der Kit-Auslieferung hineingebaut), meldet ``GET /`` das klar; die API läuft
trotzdem.
"""

from __future__ import annotations

import json
import mimetypes
import re
import threading
import time
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, unquote, urlsplit

from spec_agent_kit import __version__, contracts
from spec_agent_kit.board import BoardError
from spec_agent_kit.board.build import build_board
from spec_agent_kit.config import EffectiveConfig, load_config
from spec_agent_kit.pipeline import runs as run_store
from spec_agent_kit.pipeline.events import read_events

DEFAULT_PORT: Final[int] = 5192
FALLBACK_LAST_PORT: Final[int] = 5212
"""Ohne ausdrückliches ``--port`` wird 5192 bis 5212 der Reihe nach versucht (Spec 009 US2)."""
LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
WEB_DIR: Final[Path] = Path(__file__).resolve().parent / "web"
BOARD_TTL_S: Final[float] = 2.0
DEFAULT_EVENT_LIMIT: Final[int] = 100
_RUN_ID: Final = re.compile(r"[0-9]{3}-[0-9]{8}-[0-9]{6}(?:-[a-z0-9]{1,8})?")
_TIMESTAMP: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:[.][0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})"
)
_CSP: Final[str] = (
    "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; img-src 'self' data:; font-src 'self' data:; base-uri 'none'; "
    "form-action 'none'; frame-ancestors 'none'"
)
_TYPES: Final[dict[str, str]] = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".txt": "text/plain; charset=utf-8",
    ".map": "application/json; charset=utf-8",
}
WEB_MISSING_MESSAGE: Final[str] = (
    "Die Board-Oberfläche fehlt: board/web/index.html ist nicht vorhanden. Die Engine wurde ohne "
    "gebaute UI ausgeliefert (Kit-Repo: 'pnpm board:build', danach 'sak upgrade'). "
    "Die Lese-API unter /api/ läuft trotzdem."
)


def web_available(directory: Path | None = None) -> bool:
    """``True``, wenn die gebaute UI (``index.html``) vorhanden ist."""
    return ((directory or WEB_DIR) / "index.html").is_file()


def _content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return _TYPES.get(suffix) or mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def _json(status: int, payload: Any) -> tuple[int, str, bytes]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    return status, "application/json; charset=utf-8", body


def _not_found() -> tuple[int, str, bytes]:
    return _json(404, {"error": "not_found"})


def _utc(value: Any) -> datetime | None:
    try:
        return run_store.parse_ts(str(value))
    except ValueError:
        return None


class _LocalApi:
    """Lese-API einer Projektwurzel. Das Board wird höchstens alle ``ttl`` Sekunden neu gebaut."""

    def __init__(self, root: Path, ttl: float) -> None:
        self.root = root
        self.ttl = ttl
        self._lock = threading.Lock()
        self._built_at = float("-inf")
        self._document: dict[str, Any] | None = None

    def config(self) -> EffectiveConfig:
        return load_config(self.root)

    def board(self) -> dict[str, Any]:
        """Aktuelles Board (lokal ist der Betreff-Text immer sichtbar). Wirft bei Fehlern."""
        with self._lock:
            now = time.monotonic()
            if self._document is None or now - self._built_at >= self.ttl:
                self._document = build_board(self.root, self.config(), share_text=True)
                self._built_at = now
            return self._document

    def meta(self) -> tuple[int, str, bytes]:
        cfg = self.config()
        locale = str(cfg.data["locale"])
        try:
            table = contracts.labels(locale)
        except OSError:
            locale, table = contracts.DEFAULT_LOCALE, contracts.labels()
        return _json(
            200,
            {
                "kit_version": __version__,
                "vocabulary_version": contracts.vocabulary_version(),
                "locale": locale,
                "vocabulary": contracts.vocabulary(),
                "labels": table,
                "limits": dict(contracts.LIMITS),
                "mode": "local",
                "project_key": cfg.data["project"]["key"],
            },
        )

    def project(self, key: str) -> tuple[int, str, bytes]:
        if key != self.config().data["project"]["key"]:
            return _not_found()
        board = self.board()
        events = read_events(self.root)
        stamps = [t for t in (_utc(e.get("ts")) for e in events) if t is not None]
        last = max(stamps) if stamps else None
        return _json(
            200,
            {
                "project": {"key": board["project"]["key"], "name": board["project"]["name"]},
                "board": board,
                "ingest": {
                    "last_ingest_at": run_store.format_ts(last) if last else None,
                    "board_received_at": board["generated_at"],
                    "event_count": len(events),
                },
            },
        )

    @staticmethod
    def _ordered(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        floor = datetime.min.replace(tzinfo=UTC)

        def key(event: dict[str, Any]) -> tuple[datetime, str]:
            return (_utc(event.get("ts")) or floor, str(event.get("event_id", "")))

        return sorted(events, key=key)

    def run_detail(self, key: str, run_id: str) -> tuple[int, str, bytes]:
        if key != self.config().data["project"]["key"] or not _RUN_ID.fullmatch(run_id):
            return _not_found()
        board = self.board()
        run = next((r for r in board["runs"] if r["run_id"] == run_id), None)
        events = self._ordered(read_events(self.root, run_id))
        events = events[-contracts.LIMITS["INGEST_MAX_EVENTS"] :]
        if run is None and not events:
            return _not_found()
        return _json(200, {"project": key, "run": run, "events": events})

    def events(self, key: str, query: dict[str, list[str]]) -> tuple[int, str, bytes]:
        if key != self.config().data["project"]["key"]:
            return _not_found()

        def first(name: str) -> str | None:
            return query[name][0] if name in query else None

        run = first("run")
        if run is not None and not _RUN_ID.fullmatch(run):
            return _json(400, {"error": "invalid_run"})
        since_raw = first("since")
        since: datetime | None = None
        if since_raw is not None:
            since = _utc(since_raw) if _TIMESTAMP.fullmatch(since_raw) else None
            if since is None:
                return _json(400, {"error": "invalid_since"})
        limit = DEFAULT_EVENT_LIMIT
        limit_raw = first("limit")
        if limit_raw is not None:
            maximum = contracts.LIMITS["INGEST_MAX_EVENTS"]
            if not re.fullmatch(r"[0-9]{1,9}", limit_raw) or not 1 <= int(limit_raw) <= maximum:
                return _json(400, {"error": "invalid_limit"})
            limit = int(limit_raw)
        found = self._ordered(read_events(self.root, run))
        if since is not None:
            floor = datetime.min.replace(tzinfo=UTC)
            found = [e for e in found if (_utc(e.get("ts")) or floor) > since][:limit]
        else:
            found = found[-limit:]
        return _json(200, {"events": found})


class _LoopbackServer(ThreadingHTTPServer):
    """Kein ``SO_REUSEADDR``: unter Windows erlaubte es einen zweiten Server auf demselben Port."""

    allow_reuse_address = False


def make_server(
    root: Path,
    port: int = DEFAULT_PORT,
    *,
    ttl: float = BOARD_TTL_S,
    web_dir: Path | None = None,
) -> ThreadingHTTPServer:
    """Schreibgeschützter Server auf 127.0.0.1. ``port=0`` wählt einen freien Port.

    ``web_dir``: Ordner der gebauten UI (Default ``board/web/``); nur für Tests gedacht.
    """
    api = _LocalApi(root, ttl)
    web = (web_dir or WEB_DIR).resolve()

    class Handler(BaseHTTPRequestHandler):
        server_version = "sak-board"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Content-Security-Policy", _CSP)
            self.end_headers()
            self.wfile.write(body)

        def _refuse(self, status: int, text: str) -> None:
            self._send(status, "text/plain; charset=utf-8", text.encode("utf-8"))

        def _api(self, path: str, query: dict[str, list[str]]) -> tuple[int, str, bytes]:
            parts = [unquote(p) for p in path.split("/")[2:]]  # nach ["", "api"]
            if parts == ["meta"]:
                return api.meta()
            if len(parts) >= 2 and parts[0] == "projects":
                if len(parts) == 2:
                    return api.project(parts[1])
                if len(parts) == 4 and parts[2] == "runs":
                    return api.run_detail(parts[1], parts[3])
                if len(parts) == 3 and parts[2] == "events":
                    return api.events(parts[1], query)
            return _not_found()

        def _static(self, path: str) -> tuple[int, str, bytes]:
            if not (web / "index.html").is_file():
                return 503, "text/plain; charset=utf-8", WEB_MISSING_MESSAGE.encode("utf-8")
            relative = unquote(path).lstrip("/")
            if "\\" in relative or "\x00" in relative or ".." in relative.split("/"):
                return 404, "text/plain; charset=utf-8", b"nicht gefunden"
            target = (web / relative).resolve() if relative else web / "index.html"
            if relative and (not target.is_relative_to(web) or not target.is_file()):
                # SPA-Fallback nur für Routen ohne Dateiendung (Deep Links wie /project/x/runs/y).
                if Path(relative).suffix:
                    return 404, "text/plain; charset=utf-8", b"nicht gefunden"
                target = web / "index.html"
            return 200, _content_type(target), target.read_bytes()

        def do_GET(self) -> None:
            host = urlsplit("//" + (self.headers.get("Host") or "")).hostname or ""
            if host not in LOOPBACK_HOSTS:
                self._refuse(403, "nur lokal erreichbar")
                return
            split = urlsplit(self.path)
            path = split.path
            try:
                if path == "/api" or path.startswith("/api/"):
                    query = parse_qs(split.query, keep_blank_values=True)
                    status, content_type, body = self._api(path, query)
                elif path == "/board.json":
                    status, content_type, body = _json(200, api.board())
                else:
                    status, content_type, body = self._static(path)
            except BoardError as exc:
                status, content_type, body = _json(500, {"error": f"{exc.path}: {exc.message}"})
            except Exception as exc:  # die Seite zeigt den Grund, statt zu sterben
                status, content_type, body = _json(500, {"error": f"{type(exc).__name__}: {exc}"})
            self._send(status, content_type, body)

        def _method_not_allowed(self) -> None:
            self.send_response(405)
            self.send_header("Allow", "GET")
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _method_not_allowed

    return _LoopbackServer(("127.0.0.1", port), Handler)


def bind_server(
    root: Path,
    port: int | None,
    *,
    first: int = DEFAULT_PORT,
    last: int = FALLBACK_LAST_PORT,
) -> tuple[ThreadingHTTPServer, int | None]:
    """Server binden. Gibt ``(server, ausgewichen_von)`` zurück.

    ``port=None``: erster freier Port von ``DEFAULT_PORT`` bis ``FALLBACK_LAST_PORT``;
    ``ausgewichen_von`` ist dann ``first``, wenn ausgewichen wurde. Ein ausdrücklicher
    Port weicht nie aus: ``OSError`` wird weitergereicht.
    """
    if port is not None:
        return make_server(root, port), None
    failure: OSError | None = None
    for candidate in range(first, last + 1):
        try:
            server = make_server(root, candidate)
        except OSError as exc:
            failure = exc
            continue
        return server, (first if candidate != first else None)
    assert failure is not None
    raise failure
