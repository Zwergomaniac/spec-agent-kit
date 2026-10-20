"""Lokaler Board-Server (Spec 006 US2, FR-008, T008): Host-Prüfung, 404, 405, Seite ohne Fremdes."""

from __future__ import annotations

import http.client
import json
import re
import socket
import threading
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from spec_agent_kit import contracts
from spec_agent_kit.board.serve import PAGE, make_server, render_page
from spec_agent_kit.cli import main


@pytest.fixture
def server(board_repo: Path, fixed_now: object) -> Iterator[ThreadingHTTPServer]:
    httpd = make_server(board_repo, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


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


def test_binds_loopback_only(server: ThreadingHTTPServer) -> None:
    assert server.server_address[0] == "127.0.0.1"


def test_root_serves_the_single_page(server: ThreadingHTTPServer) -> None:
    status, headers, body = request(server, "GET", "/")
    assert status == 200 and headers["content-type"].startswith("text/html")
    assert headers["cache-control"] == "no-store"
    assert "default-src 'none'" in headers["content-security-policy"]
    page = body.decode("utf-8")
    assert "__LABELS__" not in page
    assert '"Umsetzung fertig"' in page  # Labels de sind eingebettet


def test_board_json_is_a_valid_fresh_document(server: ThreadingHTTPServer) -> None:
    status, headers, body = request(server, "GET", "/board.json?x=1")
    assert status == 200 and headers["content-type"].startswith("application/json")
    doc = json.loads(body)
    assert contracts.validate_board(doc) == []
    assert len(doc["specs"]) == 6


@pytest.mark.parametrize(
    "host", ["localhost", "localhost:5192", "127.0.0.1:5192", "[::1]:5192", "LOCALHOST"]
)
def test_loopback_hosts_are_allowed(server: ThreadingHTTPServer, host: str) -> None:
    host = host.lower()
    assert request(server, "GET", "/board.json", host=host)[0] == 200


@pytest.mark.parametrize(
    "host", ["evil.example.com", "evil.example.com:5192", "127.0.0.1.evil.com", "10.0.0.5", ""]
)
def test_foreign_host_header_is_refused(server: ThreadingHTTPServer, host: str) -> None:
    for path in ("/", "/board.json"):
        status, _, body = request(server, "GET", path, host=host)
        assert status == 403 and b"lokal" in body


@pytest.mark.parametrize("path", ["/data.json", "/board.json/", "/index.html", "/../secret", "//x"])
def test_unknown_paths_are_404(server: ThreadingHTTPServer, path: str) -> None:
    assert request(server, "GET", path)[0] == 404


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"])
def test_only_get_is_allowed(server: ThreadingHTTPServer, method: str) -> None:
    status, headers, _ = request(server, method, "/board.json")
    assert status == 405 and headers["allow"] == "GET"


def test_broken_board_is_a_500_with_reason_not_a_crash(
    server: ThreadingHTTPServer, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spec_agent_kit.board.build.__version__", "")
    status, _, body = request(server, "GET", "/board.json")
    assert status == 500 and "kit_version" in json.loads(body)["error"]
    monkeypatch.undo()
    assert request(server, "GET", "/board.json")[0] == 200


def test_page_has_no_external_resources_and_renders_via_textcontent() -> None:
    page = PAGE.read_text(encoding="utf-8")
    assert not re.search(r"""(?:src|href|action)\s*=\s*["']?(?:https?:)?//""", page)
    assert not re.search(r"url\(\s*[\"']?https?:", page)
    assert "@import" not in page
    for forbidden in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert forbidden not in page
    assert "prefers-color-scheme" in page
    assert "/board.json" in page and "setTimeout(poll, POLL_MS)" in page
    assert "POLL_MS = 5000" in page


def test_labels_cannot_break_out_of_the_script_tag(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "spec_agent_kit.board.serve.contracts.labels",
        lambda locale="de": {"stage": {"specified": "</script><script>alert(1)</script>"}},
    )
    page = render_page().decode("utf-8")
    assert "</script><script>alert" not in page
    assert page.count("</script>") == PAGE.read_text(encoding="utf-8").count("</script>")


def test_cli_rejects_a_bad_port_and_a_busy_port(
    board_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["board", "serve", "--port", "70000"]) == 2
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen(1)
        port = busy.getsockname()[1]
        assert main(["board", "serve", "--port", str(port)]) == 2
    assert "nicht nutzbar" in capsys.readouterr().out
