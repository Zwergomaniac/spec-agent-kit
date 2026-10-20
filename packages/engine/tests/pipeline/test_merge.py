"""merge: ``--no-ff``, kein Push, Abbruch und Eskalation bei Konflikt (Spec 003 FR-011)."""

from __future__ import annotations

from conftest import Repo


def approved(repo: Repo, *, content: str = "f = 1\n") -> str:
    run_id = repo.start()
    repo.write("src/feature.py", content)
    repo.commit("feat: feature")
    repo.sak("run", "state", run_id, "reviewing")
    repo.sak("run", "state", run_id, "approved")
    return run_id


def test_merge_creates_a_no_ff_commit_with_the_documented_message(repo: Repo) -> None:
    run_id = approved(repo)
    code, out = repo.sak("run", "merge", run_id)
    assert code == 0 and out["state"] == "merged" and out["base_branch"] == "main"
    assert repo.branch() == "main"
    parents = repo.git("rev-list", "--parents", "-n", "1", "HEAD").split()
    assert len(parents) == 3  # Merge-Commit: HEAD plus zwei Eltern
    subject = repo.git("log", "-1", "--format=%s").strip()
    assert subject == f"merge: 001-demo via sak pipeline ({run_id})"
    assert out["merge_commit"] == repo.git("rev-parse", "HEAD").strip()


def test_run_merged_event_carries_the_commit(repo: Repo) -> None:
    run_id = approved(repo)
    _, out = repo.sak("run", "merge", run_id)
    merged = repo.events(run_id)[-1]
    assert merged["type"] == "run.merged"
    assert merged["data"] == {"merge_commit": out["merge_commit"]}


def test_merge_never_pushes(repo: Repo) -> None:
    remote = repo.path.parent / "remote.git"
    repo.git("init", "-q", "--bare", str(remote))
    repo.git("remote", "add", "origin", str(remote))
    run_id = approved(repo)
    repo.sak("run", "merge", run_id)
    assert repo.git("ls-remote", "origin").strip() == ""


def test_merge_requires_an_approved_run(repo: Repo) -> None:
    run_id = repo.start()
    code, out = repo.sak("run", "merge", run_id)
    assert code == 1 and "freigegebene" in out["error"]


def test_merge_requires_a_clean_tree(repo: Repo) -> None:
    run_id = approved(repo)
    repo.write("loose.py", "x")
    code, out = repo.sak("run", "merge", run_id)
    assert code == 1 and "nicht sauber" in out["error"]
    assert repo.run_json(run_id)["state"] == "approved"


def test_state_command_cannot_set_merged(repo: Repo) -> None:
    run_id = approved(repo)
    code, out = repo.sak("run", "state", run_id, "merged")
    assert code == 1 and "run merge" in out["error"]


def test_merge_conflict_aborts_the_merge_and_escalates(repo: Repo) -> None:
    run_id = approved(repo, content="f = 'branch'\n")
    repo.git("switch", "-q", "main")
    repo.write("src/feature.py", "f = 'main'\n")
    repo.commit("feat: conflicting change on main")
    code, out = repo.sak("run", "merge", run_id)
    assert code == 1 and "Merge-Konflikt" in out["error"] and out["state"] == "escalated"
    assert not (repo.path / ".git" / "MERGE_HEAD").exists()
    assert repo.git("status", "--porcelain").strip() == ""
    assert repo.branch() == "001-demo"
    escalated = repo.events(run_id)[-1]
    assert escalated["type"] == "run.escalated" and "Merge-Konflikt" in escalated["data"]["reason"]
    assert repo.run_json(run_id)["state"] == "escalated"


def test_merge_with_unrelated_failure_does_not_escalate(repo: Repo) -> None:
    run_id = approved(repo)
    repo.git("switch", "-q", "main")
    repo.git("branch", "-m", "001-demo", "renamed")
    code, out = repo.sak("run", "merge", run_id)
    assert code == 1
    assert repo.run_json(run_id)["state"] == "approved"
    assert out["ok"] is False


def test_spec_number_selects_the_approved_run(repo: Repo) -> None:
    approved(repo)
    code, out = repo.sak("run", "merge", "001")
    assert code == 0 and out["state"] == "merged"
