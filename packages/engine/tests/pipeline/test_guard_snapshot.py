"""guard, snapshot, reviewer-check (Spec 003 FR-007, FR-008, US2)."""

from __future__ import annotations

from conftest import Repo


def test_core_protection_applies_even_without_project_paths(repo: Repo) -> None:
    repo.set_config(guard={"protected_paths": []})
    run_id = repo.start()
    repo.write(".spec-agent/config.yml", "schema: sak.config/1\nproject: {key: demo, name: D}\n")
    repo.commit("touch config")
    _, out = repo.sak("run", "guard", run_id)
    assert out["escalate"] is True and ".spec-agent/config.yml" in out["protected_hits"]


def test_settings_and_skills_are_protected(repo: Repo) -> None:
    run_id = repo.start()
    repo.write(".claude/settings.json", "{}")
    repo.write(".claude/skills/sak-pipeline/SKILL.md", "x")
    repo.write(".specify/memory/constitution.md", "x")
    repo.commit("touch")
    _, out = repo.sak("run", "guard", run_id)
    assert set(out["protected_hits"]) == {
        ".claude/settings.json",
        ".claude/skills/sak-pipeline/SKILL.md",
        ".specify/memory/constitution.md",
    }


def test_project_protected_paths_are_added(repo: Repo) -> None:
    run_id = repo.start()
    repo.write(".claude/commands/x.md", "x")
    repo.commit("cmd")
    _, out = repo.sak("run", "guard", run_id)
    assert out["escalate"] is True and out["protected_hits"] == [".claude/commands/x.md"]


def test_guard_without_protected_changes_does_not_escalate(repo: Repo) -> None:
    run_id = repo.start()
    repo.write("src/ok.py", "x = 1\n")
    repo.commit("ok")
    _, out = repo.sak("run", "guard", run_id)
    assert out["escalate"] is False and out["gate"] is None and out["changed_count"] == 1


def test_guard_accepts_spec_number_as_run(repo: Repo) -> None:
    run_id = repo.start()
    _, out = repo.sak("run", "guard", "001")
    assert out["run_id"] == run_id
    _, out = repo.sak("run", "guard", "001-demo")
    assert out["run_id"] == run_id


def test_reviewer_check_escalates_the_run_with_review_integrity(repo: Repo) -> None:
    run_id = repo.start()
    repo.sak("run", "state", run_id, "reviewing")
    _, snap = repo.sak("run", "snapshot")
    repo.write("src/by_reviewer.py", "x = 1\n")
    code, out = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 1 and out["gate"] == "review_integrity" and out["state"] == "escalated"
    escalated = repo.events(run_id)[-1]
    assert escalated["type"] == "run.escalated"
    assert escalated["data"]["gate"] == "review_integrity"
    assert repo.run_json(run_id)["escalation"]["gate"] == "review_integrity"


def test_snapshot_is_stable_and_detects_untracked_content(repo: Repo) -> None:
    repo.write("src/new.py", "a = 1\n")
    _, first = repo.sak("run", "snapshot")
    _, again = repo.sak("run", "snapshot")
    assert first["snapshot"] == again["snapshot"]
    repo.write("src/new.py", "a = 2\n")
    _, changed = repo.sak("run", "snapshot")
    assert changed["snapshot"] != first["snapshot"]


def test_snapshot_changes_with_head(repo: Repo) -> None:
    _, before = repo.sak("run", "snapshot")
    repo.git("commit", "-q", "--allow-empty", "-m", "empty")
    _, after = repo.sak("run", "snapshot")
    assert before["snapshot"] != after["snapshot"]


def test_reviewer_artifacts_under_state_do_not_count(repo: Repo) -> None:
    run_id = repo.start()
    _, snap = repo.sak("run", "snapshot")
    repo.write(f".spec-agent/state/runs/{run_id}/ui/screens/desktop.png", "png")
    code, _ = repo.sak("run", "reviewer-check", snap["snapshot"])
    assert code == 0
    _, guard = repo.sak("run", "guard", run_id)
    assert guard["changed_count"] == 0
