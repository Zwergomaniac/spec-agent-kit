"""Hook ``SessionStart`` mit Matcher ``compact`` (Spec 011 US8, T008)."""

from __future__ import annotations

import io
import json
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from conftest import APPROVE, CHANGES, Repo

from spec_agent_kit.cli import main
from spec_agent_kit.pipeline import session

COMPACT = json.dumps({"hook_event_name": "SessionStart", "source": "compact"})


def hook(repo: Repo, payload: str = COMPACT) -> tuple[int, dict[str, Any]]:
    return repo.sak("hook", "session-start", stdin=payload)


def context(out: dict[str, Any]) -> str:
    assert set(out) == {"hookSpecificOutput"}
    inner = out["hookSpecificOutput"]
    assert inner["hookEventName"] == "SessionStart"
    text: str = inner["additionalContext"]
    return text


def test_no_output_without_an_active_run(repo: Repo) -> None:
    code, out = hook(repo)
    assert code == 0 and out == {}


@pytest.mark.parametrize("source", ["startup", "resume", "clear", "", None])
def test_no_output_for_other_sources(repo: Repo, source: str | None) -> None:
    repo.start()
    payload = {"hook_event_name": "SessionStart"}
    if source is not None:
        payload["source"] = source
    code, out = hook(repo, json.dumps(payload))
    assert code == 0 and out == {}


@pytest.mark.parametrize("payload", ["", "kein json", "[]", '"compact"', "null", "{"])
def test_garbage_payloads_are_silent_and_exit_zero(repo: Repo, payload: str) -> None:
    repo.start()
    code, out = hook(repo, payload)
    assert code == 0 and out == {}


def test_output_for_an_active_run_after_compaction(repo: Repo) -> None:
    run_id = repo.start()
    code, out = hook(repo)
    assert code == 0
    text = context(out)
    assert run_id in text
    assert "001-demo" in text
    assert "Zustand: building, Runde 1 von 2" in text
    assert "builder=sak-builder" in text and "code_review=sak-code-reviewer" in text
    assert "Muss-Befunde der letzten Prüfung: keine." in text
    assert "Nächster Schritt:" in text and "sak-builder" in text
    assert "ohne Rückfrage" in text.replace("\n", " ")
    json.dumps(out)  # gültiges JSON


def test_the_hook_never_recommends_compacting(repo: Repo) -> None:
    repo.start()
    _, out = hook(repo)
    text = context(out).lower()
    assert "/compact" not in text and "kompaktier" in text  # nur die Feststellung, keine Empfehlung
    assert "empfehl" not in text


def test_must_findings_of_the_last_round_are_included(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    assert repo.verdict(run_id, "code_review", CHANGES, "code.md")[0] == 0
    assert repo.verdict(run_id, "ui_review", APPROVE, "ui.md")[0] == 0
    code, out = repo.sak("run", "combine", run_id)
    assert code == 0 and out["state"] == "building" and out["round"] == 2
    _, doc = hook(repo)
    text = context(doc)
    assert "Zustand: building, Runde 2 von 2" in text
    assert "Muss-Befunde der letzten Prüfung (Runde 1):" in text
    assert "[code_review]" in text and "web/style.css:880" in text
    assert "nur die Muss-Befunde" in text


def test_reviewing_lists_the_missing_verdicts(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    _, out = hook(repo)
    text = context(out)
    assert "Zustand: reviewing" in text
    assert "Es fehlen noch Urteile von: code_review, ui_review." in text


def test_escalated_run_reports_the_reason_and_waits(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "escalated", "--reason", "Migration prüfen")
    _, out = hook(repo)
    text = context(out)
    assert "Eskalation:" in text and "Migration prüfen" in text
    assert "nie selbst zurück" in text


def test_paused_run_is_not_active(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "pause", run_id, "--reason", "Limit")
    _, out = hook(repo)
    assert out == {}


def test_finished_run_is_not_active(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "abort", run_id)
    _, out = hook(repo)
    assert out == {}


def test_hook_exits_zero_outside_of_a_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO(COMPACT))
    assert main(["hook", "session-start"]) == 0
    assert capsys.readouterr().out == ""


def test_hook_gives_up_silently_after_the_deadline(
    repo: Repo, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein hängender stdin darf die Sitzung nicht aufhalten (höchstens 2 s)."""
    repo.start()
    monkeypatch.setattr(session, "DEADLINE_S", 0.2)
    release = threading.Event()

    class Blocking(io.StringIO):
        def read(self, size: int | None = -1) -> str:
            release.wait(5)
            return COMPACT

    out = io.StringIO()
    started = time.monotonic()
    session.cmd_session_start(Blocking(), repo.path, out)
    elapsed = time.monotonic() - started
    release.set()
    assert elapsed < 1.0 and out.getvalue() == ""


def test_default_deadline_is_below_two_seconds() -> None:
    assert session.DEADLINE_S <= 2.0


def test_the_hook_runs_fast_with_an_active_run(repo: Repo) -> None:
    repo.start()
    started = time.monotonic()
    code, out = hook(repo)
    assert code == 0 and out and time.monotonic() - started < 2.0


def test_hook_writes_no_events_and_no_state(repo: Repo) -> None:
    run_id = repo.start()
    before = repo.types(run_id)
    hook(repo)
    assert repo.types(run_id) == before
