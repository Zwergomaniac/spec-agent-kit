"""Nur-Prüfung: ``--review-only --base-commit`` (Spec 003 US4, Spec 001 FR-025)."""

from __future__ import annotations

from conftest import APPROVE, CHANGES, HUMAN, Repo


def prepare(repo: Repo) -> str:
    """Arbeit der Hauptsitzung: zwei Commits auf dem Basis-Branch. Gibt den Basis-Commit zurück."""
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("src/feature.py", "f = 1\n")
    repo.commit("feat: aus der Hauptsitzung")
    return base


def test_review_only_run_starts_in_reviewing_without_branch_switch(repo: Repo) -> None:
    base = prepare(repo)
    code, out = repo.sak("run", "preflight", "001", "--review-only", "--base-commit", base)
    assert code == 0, out
    assert out["kind"] == "review_only" and out["state"] == "reviewing"
    assert out["base_commit"] == base and out["branch"] == "main"
    assert set(out["roles"]) == {"code_review", "ui_review"}
    assert repo.branch() == "main"
    started = repo.events(out["run_id"])[0]
    assert started["type"] == "run.started" and started["data"]["kind"] == "review_only"
    assert started["data"]["base_commit"] == base


def test_approve_ends_as_reviewed(repo: Repo) -> None:
    base = prepare(repo)
    run_id = repo.start("001", "--review-only", "--base-commit", base)
    repo.verdict(run_id, "code_review", APPROVE, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    code, out = repo.sak("run", "combine", run_id)
    assert code == 0 and out["state"] == "reviewed"
    assert repo.types(run_id)[-1] == "run.reviewed"
    _, listed = repo.sak("run", "list")
    assert listed["runs"] == []


def test_changes_requested_escalates_instead_of_building(repo: Repo) -> None:
    base = prepare(repo)
    run_id = repo.start("001", "--review-only", "--base-commit", base)
    repo.verdict(run_id, "code_review", CHANGES, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["state"] == "escalated" and out["must"]
    assert "gate" not in repo.events(run_id)[-1]["data"]


def test_needs_human_escalates(repo: Repo) -> None:
    base = prepare(repo)
    run_id = repo.start("001", "--review-only", "--base-commit", base)
    repo.verdict(run_id, "code_review", HUMAN, "a.md")
    repo.verdict(run_id, "ui_review", APPROVE, "b.md")
    _, out = repo.sak("run", "combine", run_id)
    assert out["state"] == "escalated"


def test_review_only_run_is_not_merged_and_has_no_builder_round(repo: Repo) -> None:
    base = prepare(repo)
    run_id = repo.start("001", "--review-only", "--base-commit", base)
    code, out = repo.sak("run", "merge", run_id)
    assert code == 1 and "Nur-Prüfung" in out["error"]
    code, out = repo.sak("run", "state", run_id, "building")
    assert code == 1 and "keinen Builder" in out["error"]


def test_guard_uses_the_given_base_commit(repo: Repo) -> None:
    base = prepare(repo)
    run_id = repo.start("001", "--review-only", "--base-commit", base)
    _, out = repo.sak("run", "guard", run_id)
    assert out["changed_count"] == 1 and out["escalate"] is False


def test_unknown_base_commit_is_rejected(repo: Repo) -> None:
    code, out = repo.sak("run", "preflight", "001", "--review-only", "--base-commit", "deadbeef")
    assert code == 1 and "nicht gefunden" in out["error"]


def test_review_only_needs_a_clean_tree_and_holds_the_lock(repo: Repo) -> None:
    base = prepare(repo)
    repo.write("dirty.py", "x")
    code, _ = repo.sak("run", "preflight", "001", "--review-only", "--base-commit", base)
    assert code == 1
    (repo.path / "dirty.py").unlink()
    repo.start("001", "--review-only", "--base-commit", base)
    repo.add_spec("002-other")
    code, out = repo.sak("run", "preflight", "002")
    assert code == 1 and "läuft bereits" in out["error"]


def test_review_only_run_can_be_paused_and_resumed_without_branch_switch(repo: Repo) -> None:
    base = prepare(repo)
    run_id = repo.start("001", "--review-only", "--base-commit", base)
    repo.sak("run", "pause", run_id)
    repo.git("switch", "-q", "-c", "elsewhere")
    code, out = repo.sak("run", "resume", run_id)
    assert code == 0 and out["state"] == "reviewing" and repo.branch() == "elsewhere"
