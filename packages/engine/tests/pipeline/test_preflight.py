"""preflight: Config, Spec, Sperre, Verwaist-Erkennung, Branch (Spec 003 FR-005, FR-006)."""

from __future__ import annotations

import re

from conftest import Clock, Repo


def test_run_id_format_and_start_events(repo: Repo) -> None:
    run_id = repo.start("1")
    assert re.fullmatch(r"001-[0-9]{8}-[0-9]{6}", run_id)
    run = repo.run_json(run_id)
    assert run["kind"] == "pipeline" and run["state"] == "building" and run["paused_from"] is None
    assert run["origin"] == {"branch": "main"} and run["escalation"] is None
    assert repo.events()[1]["data"] == {"round": 1}


def test_answer_names_roles_commands_and_branch(repo: Repo) -> None:
    repo.set_config(commands={"test_fast": ["uv run pytest -q {paths}"], "lint": ["ruff check"]})
    _, out = repo.sak("run", "preflight", "001-demo")
    assert out["roles"] == {
        "builder": {"agent": "sak-builder", "model": "sonnet", "effort": "medium"},
        "code_review": {"agent": "sak-code-reviewer", "model": "opus", "effort": "medium"},
        "ui_review": {"agent": "sak-ui-reviewer", "model": "sonnet", "effort": "medium"},
    }
    assert out["commands"]["test_fast"] == ["uv run pytest -q {paths}"]
    assert out["max_rounds"] == 2 and out["base_commit"] == repo.git("rev-parse", "main").strip()


def test_inactive_role_is_not_listed(repo: Repo) -> None:
    repo.set_config(pipeline={"roles": {"ui_review": {"enabled": False}}}, ui=None)
    _, out = repo.sak("run", "preflight", "001")
    assert set(out["roles"]) == {"builder", "code_review"}


def test_schema_violation_is_rejected_with_errors(repo: Repo) -> None:
    repo.write(".spec-agent/config.yml", "schema: sak.config/1\nproject: {key: demo}\nnope: 1\n")
    repo.commit("bad config")
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and out["ok"] is False and out["errors"]


def test_config_check_failure_is_rejected(repo: Repo) -> None:
    (repo.path / ".claude/agents/sak-builder.md").unlink()
    repo.git("add", "-A")
    repo.git("commit", "-qm", "drop agent")
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and "Config ungültig" in out["error"]
    assert any("Agent-Datei fehlt" in e["message"] for e in out["errors"])


def test_without_config_everything_is_rejected_as_not_initialized(repo: Repo) -> None:
    (repo.path / ".spec-agent/config.yml").unlink()
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and "nicht initialisiert" in out["errors"][0]["message"]


def test_unknown_spec_is_rejected(repo: Repo) -> None:
    code, out = repo.sak("run", "preflight", "042")
    assert code == 1 and "042" in out["error"]


def test_stale_run_is_named_and_needs_takeover(repo: Repo, clock: Clock) -> None:
    first = repo.start()
    clock.advance(hours=7)
    repo.add_spec("002-other")
    code, out = repo.sak("run", "preflight", "002", "--base", "001-demo")
    assert code == 1
    assert first in out["error"] and "--takeover" in out["error"]
    assert out["stale_runs"][0]["run_id"] == first
    _, listed = repo.sak("run", "list")
    assert listed["stale_runs"][0]["run_id"] == first
    assert listed["runs"][0]["stale"] is True and listed["runs"][0]["idle"] is True


def test_idle_is_not_stale(repo: Repo, clock: Clock) -> None:
    first = repo.start()
    clock.advance(minutes=90)
    _, listed = repo.sak("run", "list")
    row = listed["runs"][0]
    assert row["run_id"] == first and row["idle"] is True and row["stale"] is False
    repo.add_spec("002-other")
    code, out = repo.sak("run", "preflight", "002", "--base", "001-demo", "--takeover", "Grund")
    assert code == 1 and "nicht verwaist" in out["error"]


def test_paused_run_does_not_hold_the_lock(repo: Repo) -> None:
    first = repo.start()
    repo.sak("run", "pause", first)
    repo.git("switch", "-q", "main")
    repo.add_spec("002-other")
    code, out = repo.sak("run", "preflight", "002")
    assert code == 0, out


def test_abort_then_restart_on_the_same_spec(repo: Repo, clock: Clock) -> None:
    first = repo.start()
    repo.sak("run", "abort", first, "--reason", "neu")
    clock.advance(seconds=5)
    second = repo.start()
    assert second != first
    assert repo.run_json(first)["state"] == "aborted"
    assert repo.run_json(second)["branch"] == "001-demo"


def test_run_ids_in_the_same_second_get_a_suffix(repo: Repo, clock: Clock) -> None:
    first = repo.start()
    repo.sak("run", "abort", first)
    second = repo.start()
    assert second == first + "-b"


def test_dirty_files_are_listed_and_state_dir_is_ignored(repo: Repo) -> None:
    repo.write(".spec-agent/state/note.txt", "x")
    repo.write("a.py", "1")
    repo.write("b.py", "2")
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and out["files"] == ["a.py", "b.py"]


def test_wrong_branch_is_rejected(repo: Repo) -> None:
    repo.git("switch", "-q", "-c", "feature/x")
    code, out = repo.sak("run", "preflight", "001")
    assert code == 1 and "feature/x" in out["error"]


def test_takeover_needs_a_reason_and_review_only_needs_a_commit(repo: Repo) -> None:
    code, _ = repo.sak("run", "preflight", "001", "--takeover", " ")
    assert code == 2
    code, _ = repo.sak("run", "preflight", "001", "--review-only")
    assert code == 2
    code, _ = repo.sak("run", "preflight", "001", "--base-commit", "HEAD")
    assert code == 2
