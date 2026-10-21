"""Lokaler Board-Server (Spec 006 US2, Spec 010 FR-001, A06): Lese-API, UI-Auslieferung, Schutz."""

from __future__ import annotations

import http.client
import json
import socket
import threading
from collections.abc import Callable, Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from spec_agent_kit import __version__, contracts
from spec_agent_kit.board import serve
from spec_agent_kit.board.serve import WEB_MISSING_MESSAGE, make_server
from spec_agent_kit.cli import main
from spec_agent_kit.pipeline.events import read_events

Fetch = Callable[..., tuple[int, dict[str, str], bytes]]


def start(root: Path, **kwargs: Any) -> Iterator[ThreadingHTTPServer]:
    httpd = make_server(root, 0, **kwargs)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


@pytest.fixture
def server(board_repo: Path, fixed_now: object, web_dir: Path) -> Iterator[ThreadingHTTPServer]:
    yield from start(board_repo, ttl=0)


@pytest.fixture
def server_without_ui(
    board_repo: Path, fixed_now: object, tmp_path: Path
) -> Iterator[ThreadingHTTPServer]:
    yield from start(board_repo, ttl=0, web_dir=tmp_path / "gibt-es-nicht")


def request(
    server: ThreadingHTTPServer,
    method: str,
    path: str,
    host: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        headers = {"Host": host} if host is not None else {}
        conn.request(method, path, headers=headers)
        response = conn.getresponse()
        return response.status, {k.lower(): v for k, v in response.getheaders()}, response.read()
    finally:
        conn.close()


def get_json(server: ThreadingHTTPServer, path: str) -> tuple[int, Any]:
    status, headers, body = request(server, "GET", path)
    assert headers["content-type"].startswith("application/json")
    return status, json.loads(body)


@pytest.fixture
def key(board_repo: Path) -> str:
    from spec_agent_kit.config import load_config

    return str(load_config(board_repo).data["project"]["key"])


# --- Grundschutz ------------------------------------------------------------------------------


def test_binds_loopback_only(server: ThreadingHTTPServer) -> None:
    assert server.server_address[0] == "127.0.0.1"


@pytest.mark.parametrize(
    "host", ["localhost", "localhost:5192", "127.0.0.1:5192", "[::1]:5192", "LOCALHOST"]
)
def test_loopback_hosts_are_allowed(server: ThreadingHTTPServer, host: str) -> None:
    host = host.lower()
    assert request(server, "GET", "/api/meta", host=host)[0] == 200


@pytest.mark.parametrize(
    "host", ["evil.example.com", "evil.example.com:5192", "127.0.0.1.evil.com", "10.0.0.5", ""]
)
def test_foreign_host_header_is_refused(server: ThreadingHTTPServer, host: str) -> None:
    for path in ("/", "/api/meta", "/board.json", "/assets/app.js"):
        status, _, body = request(server, "GET", path, host=host)
        assert status == 403 and b"lokal" in body


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
def test_only_get_is_allowed(server: ThreadingHTTPServer, method: str) -> None:
    for path in ("/api/meta", "/"):
        status, headers, _ = request(server, method, path)
        assert status == 405 and headers["allow"] == "GET"


# --- UI-Auslieferung --------------------------------------------------------------------------


def test_root_serves_the_built_ui(server: ThreadingHTTPServer) -> None:
    status, headers, body = request(server, "GET", "/")
    assert status == 200 and headers["content-type"].startswith("text/html")
    assert headers["cache-control"] == "no-store"
    assert "script-src 'self'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert b"<title>Board</title>" in body


def test_assets_have_matching_content_types(server: ThreadingHTTPServer) -> None:
    status, headers, body = request(server, "GET", "/assets/app.js")
    assert status == 200 and headers["content-type"].startswith("text/javascript")
    assert b"console.log" in body
    assert request(server, "GET", "/assets/app.css")[1]["content-type"].startswith("text/css")


@pytest.mark.parametrize(
    "path",
    ["/project/board-fixture", "/project/board-fixture/runs/003-20261010-090000", "/runs/x"],
)
def test_deep_links_fall_back_to_the_index(server: ThreadingHTTPServer, path: str) -> None:
    status, headers, body = request(server, "GET", path)
    assert status == 200 and headers["content-type"].startswith("text/html")
    assert b"<title>Board</title>" in body


@pytest.mark.parametrize(
    "path",
    ["/assets/fehlt.js", "/favicon.ico", "/../secret", "/%2e%2e/secret", "/a/..%2f..%2fx.js"],
)
def test_missing_files_and_traversal_are_404(server: ThreadingHTTPServer, path: str) -> None:
    assert request(server, "GET", path)[0] in {404}


def test_without_the_built_ui_the_root_says_so_and_the_api_still_works(
    server_without_ui: ThreadingHTTPServer, key: str
) -> None:
    status, headers, body = request(server_without_ui, "GET", "/")
    assert status == 503 and headers["content-type"].startswith("text/plain")
    assert body.decode("utf-8") == WEB_MISSING_MESSAGE
    assert "board/web" in WEB_MISSING_MESSAGE and "pnpm board:build" in WEB_MISSING_MESSAGE
    assert request(server_without_ui, "GET", "/deep/link")[0] == 503
    assert get_json(server_without_ui, f"/api/projects/{key}")[0] == 200


def test_cli_refuses_to_serve_without_the_built_ui(
    board_repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(serve, "WEB_DIR", board_repo / "kein-web")
    assert main(["board", "serve", "--port", "0"]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and "board/web" in out["errors"][0]["message"]


# --- Lese-API: /api/meta ----------------------------------------------------------------------


def test_meta_has_the_dashboard_shape_plus_local_mode(
    server: ThreadingHTTPServer, key: str
) -> None:
    status, meta = get_json(server, "/api/meta")
    assert status == 200
    assert set(meta) == {
        "kit_version",
        "vocabulary_version",
        "locale",
        "vocabulary",
        "labels",
        "limits",
        "mode",
        "project_key",
    }
    assert meta["mode"] == "local" and meta["project_key"] == key
    assert meta["kit_version"] == __version__
    assert meta["vocabulary_version"] == contracts.vocabulary_version() == 1
    assert meta["locale"] == "de"
    assert meta["vocabulary"] == contracts.vocabulary()
    assert meta["labels"] == contracts.labels("de")
    assert meta["limits"] == dict(contracts.LIMITS)
    assert meta["limits"]["INGEST_MAX_EVENTS"] == 500


# --- Lese-API: Projekt, Lauf, Events ----------------------------------------------------------


def test_project_has_the_dashboard_shape(
    server: ThreadingHTTPServer, board_repo: Path, key: str
) -> None:
    status, body = get_json(server, f"/api/projects/{key}")
    assert status == 200
    assert set(body) == {"project", "board", "ingest"}
    assert set(body["project"]) == {"key", "name"} and body["project"]["key"] == key
    assert contracts.validate_board(body["board"]) == []
    assert len(body["board"]["specs"]) == 6
    assert any("text" in t for t in body["board"]["ticker"])  # lokal immer sichtbar
    ingest = body["ingest"]
    assert set(ingest) == {"last_ingest_at", "board_received_at", "event_count"}
    assert ingest["event_count"] == len(read_events(board_repo)) > 0
    assert ingest["board_received_at"] == body["board"]["generated_at"]
    assert isinstance(ingest["last_ingest_at"], str)


def test_project_without_events_has_null_ingest_time(
    board_repo: Path, fixed_now: object, web_dir: Path, key: str
) -> None:
    (board_repo / ".spec-agent" / "state" / "events.jsonl").unlink()
    for httpd in start(board_repo, ttl=0):
        _, body = get_json(httpd, f"/api/projects/{key}")
        assert body["ingest"] == {
            "last_ingest_at": None,
            "board_received_at": body["board"]["generated_at"],
            "event_count": 0,
        }


@pytest.mark.parametrize(
    "path",
    [
        "/api/projects/anderes",
        "/api/projects/anderes/events",
        "/api/projects/anderes/runs/003-20261010-090000",
        "/api/portfolio",
        "/api/admin/projects",
        "/api/auth/login",
        "/api/projects",
        "/api/",
        "/api",
        "/api/projects/x/runs",
        "/api/projects/x/y/z/w",
    ],
)
def test_other_projects_portfolio_and_admin_do_not_exist_locally(
    server: ThreadingHTTPServer, path: str
) -> None:
    status, body = get_json(server, path)
    assert status == 404 and body == {"error": "not_found"}


def test_run_detail_has_the_dashboard_shape(server: ThreadingHTTPServer, key: str) -> None:
    status, body = get_json(server, f"/api/projects/{key}/runs/003-20261010-090000")
    assert status == 200
    assert set(body) == {"project", "run", "events"} and body["project"] == key
    assert body["run"]["run_id"] == "003-20261010-090000"
    assert body["events"] and all(e["run_id"] == "003-20261010-090000" for e in body["events"])
    assert all(contracts.validate_event(e) == [] for e in body["events"])
    stamps = [e["ts"] for e in body["events"]]
    assert stamps == sorted(stamps)


def test_run_detail_for_unknown_or_invalid_runs_is_404(
    server: ThreadingHTTPServer, key: str
) -> None:
    for run_id in ("999-20260101-000000", "kein-lauf", "003-20261010-090000-GROSS"):
        status, body = get_json(server, f"/api/projects/{key}/runs/{run_id}")
        assert status == 404 and body == {"error": "not_found"}


def test_events_default_lists_all_oldest_first(server: ThreadingHTTPServer, key: str) -> None:
    status, body = get_json(server, f"/api/projects/{key}/events")
    assert status == 200 and set(body) == {"events"}
    events = body["events"]
    assert events and all(contracts.validate_event(e) == [] for e in events)
    assert [e["ts"] for e in events] == sorted(e["ts"] for e in events)


def test_events_filter_by_run(server: ThreadingHTTPServer, key: str) -> None:
    _, body = get_json(server, f"/api/projects/{key}/events?run=003-20261010-090000")
    assert body["events"] and {e["run_id"] for e in body["events"]} == {"003-20261010-090000"}


def test_events_limit_without_since_returns_the_newest_ascending(
    server: ThreadingHTTPServer, key: str
) -> None:
    _, everything = get_json(server, f"/api/projects/{key}/events")
    _, newest = get_json(server, f"/api/projects/{key}/events?limit=2")
    assert newest["events"] == everything["events"][-2:]


def test_events_since_returns_the_first_events_after_it(
    server: ThreadingHTTPServer, key: str
) -> None:
    _, everything = get_json(server, f"/api/projects/{key}/events")
    first = everything["events"][0]["ts"]
    _, later = get_json(server, f"/api/projects/{key}/events?since={first}&limit=1")
    assert len(later["events"]) == 1 and later["events"][0]["ts"] > first
    _, none = get_json(server, f"/api/projects/{key}/events?since=2999-01-01T00:00:00Z")
    assert none["events"] == []


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("run=kein-lauf", "invalid_run"),
        ("run=", "invalid_run"),
        ("since=gestern", "invalid_since"),
        ("since=2026-10-10", "invalid_since"),
        ("limit=0", "invalid_limit"),
        ("limit=501", "invalid_limit"),
        ("limit=-1", "invalid_limit"),
        ("limit=abc", "invalid_limit"),
        ("limit=", "invalid_limit"),
    ],
)
def test_events_validates_the_query_like_the_dashboard(
    server: ThreadingHTTPServer, key: str, query: str, error: str
) -> None:
    status, body = get_json(server, f"/api/projects/{key}/events?{query}")
    assert status == 400 and body == {"error": error}


def test_events_limit_at_the_maximum_is_allowed(server: ThreadingHTTPServer, key: str) -> None:
    assert get_json(server, f"/api/projects/{key}/events?limit=500")[0] == 200


# --- Board-Dokument, Zwischenspeicher, Fehler -------------------------------------------------


def test_board_json_is_a_valid_fresh_document(server: ThreadingHTTPServer) -> None:
    status, doc = get_json(server, "/board.json?x=1")
    assert status == 200 and contracts.validate_board(doc) == []
    assert len(doc["specs"]) == 6


def test_board_is_rebuilt_at_most_every_ttl(
    board_repo: Path, fixed_now: object, web_dir: Path, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = []
    real = serve.build_board

    def counting(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(serve, "build_board", counting)
    for httpd in start(board_repo, ttl=60.0):
        for _ in range(3):
            assert get_json(httpd, f"/api/projects/{key}")[0] == 200
        assert len(calls) == 1
    for httpd in start(board_repo, ttl=0):
        for _ in range(2):
            assert get_json(httpd, f"/api/projects/{key}")[0] == 200
    assert len(calls) == 3


def test_changes_show_up_after_the_ttl(
    board_repo: Path, fixed_now: object, web_dir: Path, key: str
) -> None:
    for httpd in start(board_repo, ttl=0):
        _, before = get_json(httpd, f"/api/projects/{key}")
        folder = board_repo / "specs" / "007-neu"
        folder.mkdir()
        (folder / "spec.md").write_text("# Neu\n", encoding="utf-8")
        _, after = get_json(httpd, f"/api/projects/{key}")
        assert len(after["board"]["specs"]) == len(before["board"]["specs"]) + 1


def test_broken_board_is_a_500_with_reason_not_a_crash(
    server: ThreadingHTTPServer, key: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spec_agent_kit.board.build.__version__", "")
    status, body = get_json(server, f"/api/projects/{key}")
    assert status == 500 and "kit_version" in body["error"]
    monkeypatch.undo()
    assert get_json(server, f"/api/projects/{key}")[0] == 200


# --- CLI --------------------------------------------------------------------------------------


def test_cli_rejects_a_bad_port_and_a_busy_port(
    board_repo: Path, web_dir: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["board", "serve", "--port", "70000"]) == 2
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        assert main(["board", "serve", "--port", str(port)]) == 2
    assert "nicht nutzbar" in capsys.readouterr().out
