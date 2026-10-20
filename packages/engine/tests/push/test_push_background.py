"""Hintergrundstart, Auslöser in Hooks/Run-Befehlen, Hook-Dauer (Spec 006 FR-010/011, SC-003)."""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, ClassVar

import pytest
from push_support import write_config, write_events

from spec_agent_kit.cli import main
from spec_agent_kit.push import outbox
from spec_agent_kit.push import run as push_run
from spec_agent_kit.push.run import acquire_lock, spawn_background, trigger_if_auto


class FakePopen:
    calls: ClassVar[list[tuple[list[str], dict[str, Any]]]] = []

    def __init__(self, cmd: list[str], **kwargs: Any) -> None:
        FakePopen.calls.append((cmd, kwargs))


def fake_subprocess(popen: Any) -> SimpleNamespace:
    """Ersetzt nur ``push.run.subprocess``; ``subprocess.run`` für Git bleibt unberührt."""
    return SimpleNamespace(Popen=popen, DEVNULL=subprocess.DEVNULL)


@pytest.fixture
def popen(monkeypatch: pytest.MonkeyPatch) -> type[FakePopen]:
    FakePopen.calls = []
    monkeypatch.setattr(push_run, "subprocess", fake_subprocess(FakePopen))
    return FakePopen


def test_spawn_is_detached_with_devnull(project: Path, popen: type[FakePopen]) -> None:
    assert spawn_background(project) is True
    ((cmd, kwargs),) = popen.calls
    assert cmd[0] == sys.executable and cmd[-3:] == ["spec_agent_kit.cli", "push", "--quiet"]
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] == subprocess.DEVNULL and kwargs["stderr"] == subprocess.DEVNULL
    assert kwargs["cwd"] == project and kwargs["close_fds"] is True
    if os.name == "nt":
        flags = kwargs["creationflags"]
        assert flags & 0x00000008 and flags & 0x00000200 and flags & 0x08000000
        assert "start_new_session" not in kwargs
    else:
        assert kwargs["start_new_session"] is True


def test_spawn_is_skipped_while_a_push_runs(project: Path, popen: type[FakePopen]) -> None:
    assert acquire_lock(project)
    assert spawn_background(project) is False and popen.calls == []


def test_spawn_never_raises(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("kein Prozess")

    monkeypatch.setattr(push_run, "subprocess", fake_subprocess(boom))
    assert spawn_background(project) is False


def test_push_background_returns_started(
    project: Path, popen: type[FakePopen], capsys: Any
) -> None:
    assert main(["push", "--background"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "started" and len(popen.calls) == 1
    assert main(["push", "--background", "--quiet"]) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("url", "mode", "expected"),
    [
        ("http://127.0.0.1:1", "auto", True),
        ("http://127.0.0.1:1", "manual", False),
        ("http://127.0.0.1:1", "off", False),
        (None, "auto", False),
    ],
)
def test_trigger_only_for_auto_with_url(
    project: Path, popen: type[FakePopen], url: str | None, mode: str, expected: bool
) -> None:
    write_config(project, url, mode)
    assert trigger_if_auto(project) is expected
    assert len(popen.calls) == (1 if expected else 0)


def test_default_push_mode_is_auto_when_url_is_set(project: Path, popen: type[FakePopen]) -> None:
    write_config(project, "http://127.0.0.1:1", None)  # push nicht gesetzt
    assert trigger_if_auto(project) is True


def test_hook_triggers_a_background_push_and_always_exits_0(
    project: Path, popen: type[FakePopen], monkeypatch: pytest.MonkeyPatch
) -> None:
    write_config(project, "http://127.0.0.1:1", "auto")
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert main(["hook", "subagent-start"]) == 0
    assert len(popen.calls) == 1
    monkeypatch.setattr(sys, "stdin", io.StringIO("kein json"))
    assert main(["hook", "subagent-stop"]) == 0 and len(popen.calls) == 2  # kaputte Payload
    # verhindert den Push nicht; Hook endet trotzdem mit 0


def test_hook_with_manual_push_does_not_spawn(
    project: Path, popen: type[FakePopen], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert main(["hook", "subagent-start"]) == 0 and popen.calls == []


def test_hook_survives_a_failing_spawn(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    write_config(project, "http://127.0.0.1:1", "auto")

    def boom(*args: Any, **kwargs: Any) -> None:
        raise OSError("nope")

    monkeypatch.setattr(push_run, "subprocess", fake_subprocess(boom))
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    assert main(["hook", "subagent-start"]) == 0


def test_state_changing_run_commands_trigger_but_reads_do_not(
    project: Path, popen: type[FakePopen], capsys: Any
) -> None:
    write_config(project, "http://127.0.0.1:1", "auto")
    main(["run", "list"])
    main(["run", "show", "001"])
    main(["run", "snapshot"])
    assert popen.calls == []
    main(
        ["run", "pause", "001"]
    )  # scheitert (kein Lauf), löst aber aus: Events könnten entstanden sein
    main(["event", "emit", "run.paused", "--run", "001"])
    assert len(popen.calls) == 2


def test_hook_against_unreachable_dashboard_takes_under_1s_and_push_runs_in_background(
    project: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-003 mit echtem losgelöstem Prozess."""
    write_config(project, "http://127.0.0.1:1", "auto")
    write_events(project, 3)
    monkeypatch.setenv("SAK_DASHBOARD_TOKEN", "irgendwas")
    monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
    started = time.monotonic()
    code = main(["hook", "subagent-start"])
    elapsed = time.monotonic() - started
    assert code == 0 and elapsed < 1.0, elapsed
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:  # der Hintergrundprozess meldet den Fehler im Cursor
        if "nicht erreichbar" in (outbox.read_cursor(project).last_error or ""):
            break
        time.sleep(0.2)
    cursor = outbox.read_cursor(project)
    assert "nicht erreichbar" in (cursor.last_error or "")
    assert cursor.offset == 0  # Events bleiben lokal
    for _ in range(50):  # Sperre wird freigegeben
        if not push_run.lock_path(project).exists():
            break
        time.sleep(0.1)
    assert not push_run.lock_path(project).exists()


def test_hook_via_fresh_interpreter_stays_under_1s(project: Path) -> None:
    write_config(project, "http://127.0.0.1:1", "auto")
    env = dict(os.environ, SAK_DASHBOARD_TOKEN="x")
    started = time.monotonic()
    done = subprocess.run(
        [sys.executable, "-m", "spec_agent_kit.cli", "hook", "subagent-start"],
        cwd=project,
        input="{}",
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    elapsed = time.monotonic() - started
    assert done.returncode == 0 and done.stdout == ""
    assert elapsed < 1.0, elapsed
