"""pause, resume und --takeover (Spec 003 US3, Spec 001 FR-012, FR-013)."""

from __future__ import annotations

from conftest import APPROVE, Clock, Repo


def test_pause_frees_the_lock_and_remembers_the_state(repo: Repo) -> None:
    run_id = repo.start()
    code, out = repo.sak("run", "pause", run_id, "--reason", "API-Limit")
    assert code == 0 and out["state"] == "paused" and out["paused_from"] == "building"
    assert repo.run_json(run_id)["paused_from"] == "building"
    paused = repo.events(run_id)[-1]
    assert paused["type"] == "run.paused" and paused["data"] == {"reason": "API-Limit"}
    repo.git("switch", "-q", "main")
    repo.add_spec("002-other")
    code, out = repo.sak("run", "preflight", "002")
    assert code == 0, out


def test_resume_restores_branch_and_state(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "pause", run_id)
    repo.git("switch", "-q", "main")
    code, out = repo.sak("run", "resume", run_id)
    assert code == 0 and out["state"] == "building" and out["branch"] == "001-demo"
    assert repo.branch() == "001-demo"
    assert repo.types(run_id)[-1] == "run.resumed"
    assert repo.events(run_id)[-1]["data"] == {}
    assert repo.run_json(run_id)["paused_from"] is None


def test_resume_goes_back_to_reviewing(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    repo.sak("run", "pause", run_id)
    code, out = repo.sak("run", "resume", "001")
    assert code == 0 and out["state"] == "reviewing"


def test_resume_is_refused_while_another_run_is_active(repo: Repo) -> None:
    first = repo.start()
    repo.sak("run", "pause", first)
    repo.git("switch", "-q", "main")
    repo.add_spec("002-other")
    second = repo.start("002")
    code, out = repo.sak("run", "resume", first)
    assert code == 1 and second in out["error"]
    assert repo.run_json(first)["state"] == "paused"


def test_resume_needs_a_clean_tree_to_switch_branches(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "pause", run_id)
    repo.git("switch", "-q", "main")
    repo.write("dirty.py", "x")
    code, out = repo.sak("run", "resume", run_id)
    assert code == 1 and "nicht sauber" in out["error"]
    assert repo.branch() == "main" and repo.run_json(run_id)["state"] == "paused"


def test_resume_on_the_run_branch_does_not_need_a_clean_tree(repo: Repo) -> None:
    run_id = repo.start()
    repo.write("src/wip.py", "unfertig")
    repo.sak("run", "pause", run_id)
    code, _ = repo.sak("run", "resume", run_id)
    assert code == 0


def test_resume_refuses_a_run_that_is_not_paused(repo: Repo) -> None:
    run_id = repo.start()
    code, out = repo.sak("run", "resume", run_id)
    assert code == 1 and "nicht pausiert" in out["error"]


def test_several_paused_runs_are_allowed_and_resume_picks_the_requested_one(repo: Repo) -> None:
    first = repo.start()
    repo.sak("run", "pause", first)
    repo.git("switch", "-q", "main")
    repo.add_spec("002-other")
    second = repo.start("002")
    repo.sak("run", "pause", second)
    _, listed = repo.sak("run", "list")
    assert {r["state"] for r in listed["runs"]} == {"paused"} and len(listed["runs"]) == 2
    code, out = repo.sak("run", "resume", "002")
    assert code == 0 and out["run_id"] == second
    assert repo.branch() == "002-other"


def test_pause_of_an_approved_run_is_refused(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    repo.sak("run", "state", run_id, "approved")
    code, out = repo.sak("run", "pause", run_id)
    assert code == 1 and "nicht erlaubt" in out["error"]


def test_escalated_run_can_be_paused_and_stays_escalated_on_resume(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "escalated", "--reason", "Login", "--gate", "release")
    repo.sak("run", "pause", run_id)
    code, out = repo.sak("run", "resume", run_id)
    assert code == 0 and out["state"] == "escalated"
    assert repo.run_json(run_id)["escalation"]["reason"] == "Login"
    assert repo.types(run_id)[-2:] == ["run.paused", "run.resumed"]


def test_state_command_resumes_only_to_the_paused_from_state(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "pause", run_id)
    code, out = repo.sak("run", "state", run_id, "reviewing")
    assert code == 1 and "paused → reviewing" in out["error"]
    code, out = repo.sak("run", "state", run_id, "building")
    assert code == 0 and out["state"] == "building"
    repo.sak("run", "state", run_id, "paused", "--reason", "x")
    assert repo.run_json(run_id)["state"] == "paused"


def test_paused_run_can_be_aborted(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "pause", run_id)
    code, out = repo.sak("run", "abort", run_id, "--reason", "verworfen")
    assert code == 0 and out["state"] == "aborted"
    assert repo.types(run_id)[-1] == "run.aborted"
    assert repo.run_json(run_id)["paused_from"] is None


def test_spec_token_prefers_the_youngest_open_run(repo: Repo, clock: Clock) -> None:
    first = repo.start()
    repo.sak("run", "abort", first)
    clock.advance(seconds=10)
    second = repo.start()
    _, out = repo.sak("run", "show", "001-demo")
    assert out["run"]["run_id"] == second
    _, out = repo.sak("run", "show", first)
    assert out["run"]["state"] == "aborted"


# --- takeover -----------------------------------------------------------------


def test_takeover_aborts_the_stale_run_and_starts_the_new_one(repo: Repo, clock: Clock) -> None:
    old = repo.start()
    clock.advance(hours=7)
    repo.add_spec("002-other")
    code, out = repo.sak(
        "run", "preflight", "002", "--base", "001-demo", "--takeover", "Sitzung abgestürzt"
    )
    assert code == 0, out
    assert out["taken_over"] == old and out["stale_runs"] == []
    assert repo.run_json(old)["state"] == "aborted"
    taken = [e for e in repo.events(old) if e["type"] == "run.taken_over"]
    assert taken[0]["data"] == {"reason": "Sitzung abgestürzt", "previous_state": "building"}
    assert "run.aborted" not in repo.types(old)
    assert repo.run_json(out["run_id"])["state"] == "building"


def test_takeover_branch_keeps_the_old_branch(repo: Repo, clock: Clock) -> None:
    old = repo.start()
    clock.advance(hours=7)
    repo.git("switch", "-q", "main")
    repo.add_spec("002-other")
    code, out = repo.sak("run", "preflight", "002", "--takeover", "weg")
    assert code == 0, out
    assert repo.run_json(old)["branch"] == "001-demo"
    assert "001-demo" in repo.git("branch", "--list", "001-demo")


def test_takeover_of_an_escalated_stale_run(repo: Repo, clock: Clock) -> None:
    old = repo.start()
    repo.sak("run", "state", old, "escalated", "--reason", "x")
    clock.advance(hours=7)
    repo.git("switch", "-q", "main")
    repo.add_spec("002-other")
    code, _ = repo.sak("run", "preflight", "002", "--takeover", "vergessen")
    assert code == 0
    assert repo.events(old)[-1]["data"]["previous_state"] == "escalated"


def test_a_fresh_event_makes_the_run_current_again(repo: Repo, clock: Clock) -> None:
    run_id = repo.start()
    clock.advance(hours=7)
    repo.sak("hook", "subagent-start", stdin='{"agent_type": "sak-builder"}')
    _, listed = repo.sak("run", "list")
    assert listed["runs"][0]["run_id"] == run_id and listed["runs"][0]["stale"] is False


def test_takeover_without_an_active_run_just_starts(repo: Repo) -> None:
    code, out = repo.sak("run", "preflight", "001", "--takeover", "unnötig")
    assert code == 0 and out["taken_over"] is None


def test_stale_thresholds_come_from_the_config(repo: Repo, clock: Clock) -> None:
    repo.set_config(pipeline={"stale_hours": 1, "idle_minutes": 5})
    run_id = repo.start()
    clock.advance(minutes=10)
    _, listed = repo.sak("run", "list")
    assert listed["runs"][0]["idle"] is True and listed["runs"][0]["stale"] is False
    clock.advance(hours=1)
    _, listed = repo.sak("run", "list")
    assert listed["runs"][0]["stale"] is True and listed["runs"][0]["run_id"] == run_id


def test_paused_and_finished_runs_are_never_stale(repo: Repo, clock: Clock) -> None:
    run_id = repo.start()
    repo.sak("run", "pause", run_id)
    clock.advance(hours=48)
    _, listed = repo.sak("run", "list")
    assert listed["runs"][0]["stale"] is False and listed["stale_runs"] == []


def test_verdicts_survive_a_pause(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    repo.verdict(run_id, "code_review", APPROVE, "a.md")
    repo.sak("run", "pause", run_id)
    repo.sak("run", "resume", run_id)
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 0 and out["state"] == "approved"
