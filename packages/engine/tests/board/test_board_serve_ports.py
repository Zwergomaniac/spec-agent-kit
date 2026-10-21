"""Port-Ausweichen und ``--open`` von ``sak board serve`` (Spec 009 US2, A04).

Die Tests belegen nur selbst gewählte Ports in einem Bereich, den sie vorher als frei erkannt haben;
der echte Default 5192 wird nie angefasst.
"""

from __future__ import annotations

import contextlib
import json
import socket
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from spec_agent_kit import cli
from spec_agent_kit.board import serve
from spec_agent_kit.board.serve import bind_server

pytestmark = pytest.mark.usefixtures("web_dir")


def _free_range(width: int = 4) -> int:
    """Erster Port einer zusammenhängenden freien Strecke der Breite ``width``."""
    for _ in range(50):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            base = probe.getsockname()[1]
        if base + width > 65000:
            continue
        sockets: list[socket.socket] = []
        try:
            for offset in range(width):
                s = socket.socket()
                sockets.append(s)
                s.bind(("127.0.0.1", base + offset))
        except OSError:
            continue
        finally:
            for s in sockets:
                s.close()
        return base
    pytest.skip("keine freie Portstrecke gefunden")


@pytest.fixture
def busy_first() -> Iterator[tuple[int, socket.socket]]:
    base = _free_range()
    holder = socket.socket()
    holder.bind(("127.0.0.1", base))
    holder.listen(1)
    yield base, holder
    holder.close()


def test_default_range_matches_the_spec() -> None:
    assert (serve.DEFAULT_PORT, serve.FALLBACK_LAST_PORT) == (5192, 5212)


def test_free_first_port_is_used_without_moving(board_repo: Path) -> None:
    base = _free_range()
    server, moved = bind_server(board_repo, None, first=base, last=base + 3)
    try:
        assert server.server_address[1] == base and moved is None
    finally:
        server.server_close()


def test_busy_first_port_moves_to_the_next_free_one(
    board_repo: Path, busy_first: tuple[int, socket.socket]
) -> None:
    base, _ = busy_first
    server, moved = bind_server(board_repo, None, first=base, last=base + 3)
    try:
        assert server.server_address[1] == base + 1 and moved == base
    finally:
        server.server_close()


def test_all_busy_raises(board_repo: Path, busy_first: tuple[int, socket.socket]) -> None:
    base, _ = busy_first
    with pytest.raises(OSError):
        bind_server(board_repo, None, first=base, last=base)


def test_explicit_port_never_moves(board_repo: Path, busy_first: tuple[int, socket.socket]) -> None:
    base, _ = busy_first
    with pytest.raises(OSError):
        bind_server(board_repo, base)


@pytest.fixture
def no_serving(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """``serve_forever`` kehrt sofort zurück; ``webbrowser.open`` wird nur protokolliert."""
    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", lambda self, *a, **k: None)
    opened: list[str] = []
    monkeypatch.setattr(cli.webbrowser, "open", lambda url, *a, **k: opened.append(url) or True)
    return opened


def _ranged(monkeypatch: pytest.MonkeyPatch, base: int) -> None:
    original = cli.bind_server
    monkeypatch.setattr(
        cli,
        "bind_server",
        lambda root, port: original(root, port, first=base, last=base + 3),
    )


def test_cli_without_port_moves_and_reports_the_url(
    board_repo: Path,
    busy_first: tuple[int, socket.socket],
    no_serving: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base, _ = busy_first
    _ranged(monkeypatch, base)
    assert cli.main(["board", "serve"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True and out["url"] == f"http://127.0.0.1:{base + 1}"
    assert out["port_busy"] == base
    assert no_serving == []  # ohne --open kein Browser


def test_cli_open_opens_the_browser_with_the_url(
    board_repo: Path,
    no_serving: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _ranged(monkeypatch, _free_range())
    assert cli.main(["board", "serve", "--open"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert no_serving == [out["url"]]
    assert "port_busy" not in out


def test_cli_open_failure_does_not_break_the_server(
    board_repo: Path,
    no_serving: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(url: str) -> bool:
        raise RuntimeError("kein Browser")

    monkeypatch.setattr(cli.webbrowser, "open", boom)
    _ranged(monkeypatch, _free_range())
    assert cli.main(["board", "serve", "--open"]) == 0


def test_cli_explicit_busy_port_is_exit_2_without_moving(
    board_repo: Path,
    busy_first: tuple[int, socket.socket],
    no_serving: list[str],
    capsys: pytest.CaptureFixture[str],
) -> None:
    base, _ = busy_first
    assert cli.main(["board", "serve", "--port", str(base), "--open"]) == 2
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and f"Port {base} nicht nutzbar" in out["error"]
    assert no_serving == []


def test_cli_all_default_ports_busy_is_exit_2(
    board_repo: Path,
    busy_first: tuple[int, socket.socket],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    base, _ = busy_first
    original = cli.bind_server
    monkeypatch.setattr(
        cli, "bind_server", lambda root, port: original(root, port, first=base, last=base)
    )
    assert cli.main(["board", "serve"]) == 2
    assert "kein freier Port" in json.loads(capsys.readouterr().out)["error"]


def test_help_names_the_new_behaviour(capsys: pytest.CaptureFixture[str]) -> None:
    with contextlib.suppress(SystemExit):
        cli.main(["board", "serve", "--help"])
    text = capsys.readouterr().out
    assert "--open" in text and "5212" in text
