"""Hooks SubagentStart und SubagentStop (Spec 003 FR-012, US5)."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from conftest import Clock, Repo

from spec_agent_kit.pipeline import hooks


def payload(agent: str) -> str:
    return json.dumps({"agent_type": agent})


def test_duration_comes_from_the_clock(repo: Repo, clock: Clock) -> None:
    run_id = repo.start()
    repo.sak("hook", "subagent-start", stdin=payload("sak-ui-reviewer"))
    clock.advance(seconds=42)
    repo.sak("hook", "subagent-stop", stdin=payload("sak-ui-reviewer"))
    finished = repo.events(run_id)[-1]
    assert finished["type"] == "station.finished" and finished["data"]["duration_s"] == 42
    assert finished["data"]["role"] == "ui_review"


def test_open_stations_are_tracked_and_cleared(repo: Repo) -> None:
    run_id = repo.start()
    store = repo.path / f".spec-agent/state/runs/{run_id}/open-stations.json"
    repo.sak("hook", "subagent-start", stdin=payload("sak-code-reviewer"))
    repo.sak("hook", "subagent-start", stdin=payload("sak-ui-reviewer"))
    assert set(json.loads(store.read_text(encoding="utf-8"))) == {
        "sak-code-reviewer",
        "sak-ui-reviewer",
    }
    repo.sak("hook", "subagent-stop", stdin=payload("sak-code-reviewer"))
    assert set(json.loads(store.read_text(encoding="utf-8"))) == {"sak-ui-reviewer"}


def test_stop_without_start_writes_zero_duration(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("hook", "subagent-stop", stdin=payload("sak-builder"))
    assert repo.events(run_id)[-1]["data"]["duration_s"] == 0


def test_round_is_taken_from_the_run(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    repo.sak("run", "state", run_id, "building")
    repo.sak("hook", "subagent-start", stdin=payload("sak-builder"))
    assert repo.events(run_id)[-1]["data"]["round"] == 2


def test_agent_names_come_from_the_config(repo: Repo) -> None:
    repo.write(
        ".claude/agents/pruefer.md", "---\nname: pruefer\nmodel: opus\neffort: medium\n---\nx\n"
    )
    repo.set_config(pipeline={"roles": {"code_review": {"agent": "pruefer"}}})
    run_id = repo.start()
    repo.sak("hook", "subagent-start", stdin=payload("pruefer"))
    assert repo.events(run_id)[-1]["data"]["role"] == "code_review"
    before = len(repo.events())
    repo.sak("hook", "subagent-start", stdin=payload("sak-code-reviewer"))
    assert len(repo.events()) == before


def test_inactive_role_is_ignored(repo: Repo) -> None:
    repo.set_config(pipeline={"roles": {"ui_review": {"enabled": False}}}, ui=None)
    repo.start()
    before = len(repo.events())
    repo.sak("hook", "subagent-start", stdin=payload("sak-ui-reviewer"))
    assert len(repo.events()) == before


def test_paused_run_gets_no_station_events(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "pause", run_id)
    before = len(repo.events())
    repo.sak("hook", "subagent-start", stdin=payload("sak-builder"))
    assert len(repo.events()) == before


def test_diag_hook_is_written_once_per_phase(repo: Repo) -> None:
    repo.start()
    for phase in ("subagent-start", "subagent-start", "subagent-stop", "subagent-stop"):
        repo.sak("hook", phase, stdin=json.dumps({"b": 1, "a": 2}))
    diag = [e for e in repo.events() if e["type"] == "diag.hook"]
    assert [e["data"]["phase"] for e in diag] == ["start", "stop"]
    assert diag[0]["data"]["keys"] == ["a", "b"]


def test_diag_hook_limits_the_number_of_keys(repo: Repo) -> None:
    repo.start()
    repo.sak("hook", "subagent-start", stdin=json.dumps({f"k{i:03d}": 1 for i in range(80)}))
    diag = next(e for e in repo.events() if e["type"] == "diag.hook")
    assert len(diag["data"]["keys"]) == 50


def test_hook_prints_nothing(repo: Repo, capsys: pytest.CaptureFixture[str]) -> None:
    repo.start()
    code, out = repo.sak("hook", "subagent-start", stdin=payload("sak-builder"))
    assert code == 0 and out == {}


def test_hook_exit_code_is_zero_for_a_bad_subcommand(repo: Repo) -> None:
    code, _ = repo.sak("hook", "subagent-nonsense")
    assert code == 0
    code, _ = repo.sak("hook")
    assert code == 0


def test_hook_without_any_project_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    proc = subprocess.run(
        [
            sys.executable,
            "-c",
            "from spec_agent_kit.cli import main; raise SystemExit(main())",
            "hook",
            "subagent-start",
        ],
        input="{}",
        capture_output=True,
        text=True,
        cwd=tmp_path,
        check=False,
    )
    assert proc.returncode == 0 and proc.stdout == ""


def test_hook_never_raises_even_if_the_state_store_is_broken(repo: Repo) -> None:
    run_id = repo.start()
    store = repo.path / f".spec-agent/state/runs/{run_id}/open-stations.json"
    store.write_text("{not json", encoding="utf-8")
    code, _ = repo.sak("hook", "subagent-stop", stdin=payload("sak-builder"))
    assert code == 0


def test_hook_never_raises_for_an_invalid_event(repo: Repo) -> None:
    """Ein Event, das den Vertrag verletzt, wird nicht geschrieben; der Hook bleibt still."""
    repo.set_config(pipeline={"roles": {"builder": {"model": "m" * 200}}})
    repo.write(
        ".claude/agents/sak-builder.md",
        f"---\nname: sak-builder\nmodel: {'m' * 200}\neffort: medium\n---\nx\n",
    )
    repo.commit("long model")
    repo.start()
    before = len(repo.events())
    code, _ = repo.sak("hook", "subagent-start", stdin=payload("sak-builder"))
    assert code == 0 and len(repo.events()) == before


def test_parallel_starts_do_not_lose_stations(repo: Repo) -> None:
    run_id = repo.start()
    store = repo.path / f".spec-agent/state/runs/{run_id}/open-stations.json"

    def start(agent: str) -> None:
        hooks.cmd_hook("start", __import__("io").StringIO(payload(agent)), repo.path)

    threads = [
        threading.Thread(target=start, args=(a,)) for a in ("sak-code-reviewer", "sak-ui-reviewer")
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert set(json.loads(store.read_text(encoding="utf-8"))) == {
        "sak-code-reviewer",
        "sak-ui-reviewer",
    }


def test_hook_finishes_well_within_two_seconds(repo: Repo) -> None:
    repo.start()
    began = time.monotonic()
    repo.sak("hook", "subagent-start", stdin=payload("sak-builder"))
    assert time.monotonic() - began < 2.0


def test_agent_type_shapes() -> None:
    assert hooks.agent_type({"agent_type": "a"}) == "a"
    assert hooks.agent_type({"subagent_type": "b"}) == "b"
    assert hooks.agent_type({"tool_input": {"subagent_type": "c"}}) == "c"
    assert hooks.agent_type({"agent_type": 5}) is None
    assert hooks.agent_type({"tool_input": "x"}) is None
