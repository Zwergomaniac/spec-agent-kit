"""Lokale Ansicht: ``sak board serve`` (Spec 006 FR-008, Port von ``make_server``).

Nur ``127.0.0.1``, nur ``GET /`` und ``GET /board.json``, Host-Header-Prüfung gegen DNS-Rebinding.
Die Seite ist eine einzelne HTML-Datei ohne externe Ressourcen; die Labels der Locale werden
eingebettet.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Final
from urllib.parse import urlsplit

from spec_agent_kit import contracts
from spec_agent_kit.board import BoardError
from spec_agent_kit.board.build import build_board
from spec_agent_kit.config import EffectiveConfig, load_config

DEFAULT_PORT: Final[int] = 5192
LOOPBACK_HOSTS: Final[frozenset[str]] = frozenset({"127.0.0.1", "localhost", "::1"})
PAGE: Final[Path] = Path(__file__).resolve().parent / "static" / "board.html"
_PLACEHOLDER: Final[str] = "__LABELS__"
_CSP: Final[str] = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "connect-src 'self'; img-src data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
)


def render_page(locale: str = contracts.DEFAULT_LOCALE) -> bytes:
    """Die HTML-Seite mit eingebetteten Labels (``<`` wird maskiert, damit nichts ausbricht)."""
    try:
        table = contracts.labels(locale)
    except OSError:
        table = contracts.labels()
    embedded = json.dumps(table, ensure_ascii=False).replace("<", "\\u003c")
    return PAGE.read_text(encoding="utf-8").replace(_PLACEHOLDER, embedded).encode("utf-8")


class _LoopbackServer(ThreadingHTTPServer):
    """Kein ``SO_REUSEADDR``: unter Windows erlaubte es einen zweiten Server auf demselben Port."""

    allow_reuse_address = False


def make_server(root: Path, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Schreibgeschützter Server auf 127.0.0.1. ``port=0`` wählt einen freien Port."""

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

        def _board_body(self) -> tuple[int, bytes]:
            try:
                cfg: EffectiveConfig = load_config(root)
                document = build_board(root, cfg, share_text=True)
            except BoardError as exc:
                return 500, json.dumps({"error": f"{exc.path}: {exc.message}"}).encode("utf-8")
            except Exception as exc:  # die Seite zeigt den Grund, statt zu sterben
                return 500, json.dumps({"error": f"{type(exc).__name__}: {exc}"}).encode("utf-8")
            return 200, json.dumps(document, ensure_ascii=False).encode("utf-8")

        def do_GET(self) -> None:
            host = urlsplit("//" + (self.headers.get("Host") or "")).hostname or ""
            if host not in LOOPBACK_HOSTS:
                self._refuse(403, "nur lokal erreichbar")
                return
            path = self.path.split("?", 1)[0]
            if path == "/":
                try:
                    locale = str(load_config(root).data["locale"])
                except Exception:
                    locale = contracts.DEFAULT_LOCALE
                try:
                    self._send(200, "text/html; charset=utf-8", render_page(locale))
                except OSError:
                    self._refuse(500, "Seite board.html fehlt")
            elif path == "/board.json":
                status, body = self._board_body()
                self._send(status, "application/json; charset=utf-8", body)
            else:
                self._refuse(404, "nicht gefunden")

        def _method_not_allowed(self) -> None:
            self.send_response(405)
            self.send_header("Allow", "GET")
            self.send_header("Content-Length", "0")
            self.end_headers()

        do_POST = do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = _method_not_allowed

    return _LoopbackServer(("127.0.0.1", port), Handler)
