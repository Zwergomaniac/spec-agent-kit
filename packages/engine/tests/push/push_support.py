"""Lokaler Test-Server (Dashboard-Attrappe) und Hilfen für die Push-Tests (Spec 006, T013)."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import yaml

from spec_agent_kit import contracts

KEY = "test-key-123"


class FakeDashboard:
    """Verhält sich wie ``apps/dashboard-api``: dedupliziert per ``event_id``, prüft Bearer."""

    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.seen: set[str] = set()
        self.boards: list[dict[str, Any]] = []
        self.auth_status: int | None = None  # z. B. 401 erzwingen
        self.raw_status: tuple[int, dict[str, Any]] | None = None  # ganze Anfrage ablehnen
        self.reject: Callable[[dict[str, Any]], str | None] = lambda event: None
        self.board_error: str | None = None
        self.redirect_to: str | None = None
        self.auth_headers: list[str | None] = []  # Authorization je Anfrage (None = fehlt)
        self.proxy_injects = False  # wie ein Proxy mit Network Secret: setzt den Bearer selbst
        self.lock = threading.Lock()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def start(self) -> FakeDashboard:
        self.thread.start()
        return self

    def enable_tls(self, certfile: Path, keyfile: Path) -> None:
        """Vor ``start`` aufrufen: der Server spricht dann HTTPS (nur Loopback)."""
        import ssl

        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(certfile), str(keyfile))
        self.httpd.socket = context.wrap_socket(self.httpd.socket, server_side=True)

    @property
    def tls_url(self) -> str:
        return f"https://127.0.0.1:{self.httpd.server_address[1]}"

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)

    def _handler(self) -> type[BaseHTTPRequestHandler]:
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:
                return

            def _json(self, status: int, body: dict[str, Any]) -> None:
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length)
                received = self.headers.get("Authorization")
                outer.auth_headers.append(received)
                effective = (
                    f"Bearer {KEY}" if outer.proxy_injects and received is None else received
                )
                if outer.redirect_to:
                    self.send_response(302)
                    self.send_header("Location", outer.redirect_to)
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                if outer.auth_status or effective != f"Bearer {KEY}":
                    self._json(outer.auth_status or 401, {"error": "unauthorized"})
                    return
                if outer.raw_status:
                    self._json(*outer.raw_status)
                    return
                body = json.loads(raw)
                with outer.lock:
                    outer.requests.append(body)
                    accepted = duplicates = 0
                    rejected: list[dict[str, str]] = []
                    for event in body["events"]:
                        reason = outer.reject(event)
                        if reason:
                            rejected.append({"event_id": event["event_id"], "error": reason})
                        elif event["event_id"] in outer.seen:
                            duplicates += 1
                        else:
                            outer.seen.add(event["event_id"])
                            accepted += 1
                    board_accepted = False
                    if "board" in body:
                        if outer.board_error:
                            rejected.append({"error": outer.board_error})
                        else:
                            outer.boards.append(body["board"])
                            board_accepted = True
                self._json(
                    200,
                    {
                        "schema": "sak.ingest_result/1",
                        "accepted": accepted,
                        "duplicates": duplicates,
                        "rejected": rejected,
                        "board_accepted": board_accepted,
                    },
                )

        return Handler


def make_event(n: int = 0, project: str = "demo") -> dict[str, Any]:
    event = {
        "schema": "sak.event/1",
        "event_id": contracts.new_ulid(),
        "type": "round.started",
        "ts": "2026-10-10T09:00:00Z",
        "project": project,
        "run_id": "001-20261010-090000",
        "spec": "001-demo",
        "data": {"round": 1},
    }
    assert contracts.validate_event(event) == []
    return event


def write_events(root: Path, count: int, *, append: bool = True) -> list[dict[str, Any]]:
    path = root / ".spec-agent" / "state" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    events = [make_event(i) for i in range(count)]
    with path.open("a" if append else "w", encoding="utf-8", newline="\n") as handle:
        for event in events:
            handle.write(json.dumps(event, separators=(",", ":")) + "\n")
    return events


def write_config(root: Path, url: str | None, push: str | None = "manual") -> None:
    dashboard: dict[str, Any] = {"url": url}
    if push:
        dashboard["push"] = push
    data = {
        "schema": "sak.config/1",
        "project": {"key": "demo", "name": "Demo"},
        "pipeline": {"roles": {"ui_review": {"enabled": False}}},
        "dashboard": dashboard,
    }
    (root / ".spec-agent").mkdir(parents=True, exist_ok=True)
    (root / ".spec-agent" / "config.yml").write_text(yaml.safe_dump(data), encoding="utf-8")
